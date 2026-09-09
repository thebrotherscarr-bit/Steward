//! Safe SQLite driver over the winsqlite3 FFI (THE_CATALOG S-row).
//!
//! RAII owns every handle: Statement finalizes on drop, Conn closes_v2 on
//! drop. Errors carry SQLite's own message (UTF-16 errmsg16), never a
//! paraphrase. The connection law (SPEC_SQLITE §Connection law) is applied
//! through one audited call: WAL, synchronous=FULL, foreign_keys ON,
//! busy_timeout set — and the observed values come back so strokes can pin
//! them.

use std::ffi::CString;
use std::path::Path;

use crate::ffi;

#[derive(Debug, Clone)]
pub struct StoreError {
    pub code: i32,
    pub msg: String,
}

impl std::fmt::Display for StoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "sqlite error {}: {}", self.code, self.msg)
    }
}

impl std::error::Error for StoreError {}

pub type Result<T> = std::result::Result<T, StoreError>;

pub struct Conn {
    db: ffi::Db,
}

/// The connection law, observed after application. Stroke material.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConnectionLaw {
    pub journal_mode: String,
    pub synchronous: String,
    pub foreign_keys: String,
    pub busy_timeout_ms: i64,
}

impl Conn {
    fn open_with(path: &Path, flags: i32) -> Result<Conn> {
        let cpath = CString::new(path.to_str().ok_or_else(|| StoreError {
            code: -1,
            msg: "path is not valid UTF-8".into(),
        })?)
        .map_err(|_| StoreError {
            code: -1,
            msg: "path contains NUL".into(),
        })?;
        let mut db: ffi::Db = std::ptr::null_mut();
        let rc = unsafe {
            ffi::sqlite3_open_v2(cpath.as_ptr(), &mut db, flags, std::ptr::null())
        };
        if rc != ffi::SQLITE_OK {
            // Even on failure the handle may carry a message; close it.
            let msg = if db.is_null() {
                format!("open failed rc={}", rc)
            } else {
                let m = unsafe { errmsg16(db) };
                unsafe { ffi::sqlite3_close_v2(db) };
                m
            };
            return Err(StoreError { code: rc, msg });
        }
        Ok(Conn { db })
    }

    /// Read-write connection; creates the file when absent.
    pub fn open(path: &Path) -> Result<Conn> {
        Self::open_with(
            path,
            ffi::SQLITE_OPEN_READWRITE
                | ffi::SQLITE_OPEN_CREATE
                | ffi::SQLITE_OPEN_FULLMUTEX,
        )
    }

    /// Read-only connection — refuses to create.
    pub fn open_readonly(path: &Path) -> Result<Conn> {
        Self::open_with(
            path,
            ffi::SQLITE_OPEN_READONLY | ffi::SQLITE_OPEN_FULLMUTEX,
        )
    }

    /// The SPEC_SQLITE connection law, applied and then OBSERVED.
    pub fn apply_connection_law(&self) -> Result<ConnectionLaw> {
        self.exec("PRAGMA journal_mode=WAL;")?;
        self.exec("PRAGMA synchronous=FULL;")?;
        self.exec("PRAGMA foreign_keys=ON;")?;
        unsafe { ffi::sqlite3_busy_timeout(self.db, 5000) };
        // PRAGMA synchronous reports an INTEGER (0 off, 1 normal, 2 full);
        // normalize so strokes can pin the word, like journal_mode does.
        let sync_raw = self.pragma_text("synchronous")?;
        let synchronous = match sync_raw.as_str() {
            "2" => "full".to_string(),
            "3" => "extra".to_string(),
            "1" => "normal".to_string(),
            "0" => "off".to_string(),
            other => other.to_string(),
        };
        let law = ConnectionLaw {
            journal_mode: self.pragma_text("journal_mode")?,
            synchronous,
            foreign_keys: self.pragma_text("foreign_keys")?,
            busy_timeout_ms: {
                let s = self.query_one_row("PRAGMA busy_timeout")?;
                s.parse().unwrap_or(0)
            },
        };
        Ok(law)
    }

    fn pragma_text(&self, name: &str) -> Result<String> {
        let sql = format!("PRAGMA {}", name);
        let stmt = self.prepare(&sql)?;
        match stmt.step()? {
            Step::Row => stmt.text(0),
            Step::Done => Ok(String::new()),
        }
    }

    pub fn exec(&self, sql: &str) -> Result<()> {
        let csql = CString::new(sql).map_err(|_| StoreError {
            code: -1,
            msg: "sql contains NUL".into(),
        })?;
        let rc =
            unsafe { ffi::sqlite3_exec(self.db, csql.as_ptr(), None, std::ptr::null_mut(), std::ptr::null_mut()) };
        if rc != ffi::SQLITE_OK {
            return Err(self.error(rc));
        }
        Ok(())
    }

    pub fn prepare(&self, sql: &str) -> Result<Statement<'_>> {
        let csql = CString::new(sql).map_err(|_| StoreError {
            code: -1,
            msg: "sql contains NUL".into(),
        })?;
        let mut raw: ffi::Stmt = std::ptr::null_mut();
        let rc = unsafe {
            ffi::sqlite3_prepare_v2(
                self.db,
                csql.as_ptr(),
                -1,
                &mut raw,
                std::ptr::null_mut(),
            )
        };
        if rc != ffi::SQLITE_OK {
            return Err(self.error(rc));
        }
        Ok(Statement { raw, conn: self })
    }

    /// First row of a single-row query as strings (NULL -> empty).
    fn query_one_row(&self, sql: &str) -> Result<String> {
        let stmt = self.prepare(sql)?;
        match stmt.step()? {
            Step::Row => stmt.text(0),
            Step::Done => Ok(String::new()),
        }
    }

    pub fn error(&self, code: i32) -> StoreError {
        StoreError {
            code,
            msg: unsafe { errmsg16(self.db) },
        }
    }

    pub fn changes(&self) -> usize {
        unsafe { ffi::sqlite3_changes(self.db) as usize }
    }

    pub fn last_insert_rowid(&self) -> i64 {
        unsafe { ffi::sqlite3_last_insert_rowid(self.db) }
    }

    /// SPEC_SQLITE §5: PASSIVE checkpoint after each wrap close.
    /// Returns (log frames, checkpointed frames).
    pub fn wal_checkpoint_passive(&self) -> Result<(i32, i32)> {
        let mut log: i32 = 0;
        let mut ckpt: i32 = 0;
        let rc = unsafe {
            ffi::sqlite3_wal_checkpoint_v2(
                self.db,
                std::ptr::null(),
                ffi::CHECKPOINT_PASSIVE,
                &mut log,
                &mut ckpt,
            )
        };
        if rc != ffi::SQLITE_OK {
            return Err(self.error(rc));
        }
        Ok((log, ckpt))
    }
}

impl Drop for Conn {
    fn drop(&mut self) {
        if !self.db.is_null() {
            unsafe { ffi::sqlite3_close_v2(self.db) };
            self.db = std::ptr::null_mut();
        }
    }
}

unsafe fn errmsg16(db: ffi::Db) -> String {
    let wide = ffi::sqlite3_errmsg16(db);
    if wide.is_null() {
        return String::new();
    }
    let mut len = 0usize;
    while *wide.add(len) != 0 {
        len += 1;
    }
    let buf = std::slice::from_raw_parts(wide, len);
    String::from_utf16_lossy(buf)
}

pub enum Step {
    Row,
    Done,
}

pub struct Statement<'c> {
    raw: ffi::Stmt,
    conn: &'c Conn,
}

impl Statement<'_> {
    pub fn bind_int64(&self, idx: usize, v: i64) -> Result<()> {
        let rc = unsafe { ffi::sqlite3_bind_int64(self.raw, idx as i32, v) };
        self.bind_rc(rc)
    }

    pub fn bind_double(&self, idx: usize, v: f64) -> Result<()> {
        let rc = unsafe { ffi::sqlite3_bind_double(self.raw, idx as i32, v) };
        self.bind_rc(rc)
    }

    pub fn bind_text(&self, idx: usize, v: &str) -> Result<()> {
        let rc = unsafe {
            ffi::sqlite3_bind_text(
                self.raw,
                idx as i32,
                v.as_ptr() as *const std::os::raw::c_char,
                v.len() as i32,
                ffi::SQLITE_TRANSIENT,
            )
        };
        self.bind_rc(rc)
    }

    pub fn bind_blob(&self, idx: usize, v: &[u8]) -> Result<()> {
        let rc = unsafe {
            ffi::sqlite3_bind_blob(
                self.raw,
                idx as i32,
                v.as_ptr() as *const std::os::raw::c_void,
                v.len() as i32,
                ffi::SQLITE_TRANSIENT,
            )
        };
        self.bind_rc(rc)
    }

    pub fn bind_null(&self, idx: usize) -> Result<()> {
        let rc = unsafe { ffi::sqlite3_bind_null(self.raw, idx as i32) };
        self.bind_rc(rc)
    }

    fn bind_rc(&self, rc: i32) -> Result<()> {
        if rc != ffi::SQLITE_OK {
            return Err(self.conn.error(rc));
        }
        Ok(())
    }

    pub fn step(&self) -> Result<Step> {
        let rc = unsafe { ffi::sqlite3_step(self.raw) };
        match rc {
            ffi::SQLITE_ROW => Ok(Step::Row),
            ffi::SQLITE_DONE => Ok(Step::Done),
            _ => Err(self.conn.error(rc)),
        }
    }

    pub fn reset(&self) -> Result<()> {
        let rc = unsafe { ffi::sqlite3_reset(self.raw) };
        if rc != ffi::SQLITE_OK {
            return Err(self.conn.error(rc));
        }
        unsafe { ffi::sqlite3_clear_bindings(self.raw) };
        Ok(())
    }

    pub fn column_count(&self) -> usize {
        unsafe { ffi::sqlite3_column_count(self.raw) as usize }
    }

    pub fn column_type(&self, col: usize) -> i32 {
        unsafe { ffi::sqlite3_column_type(self.raw, col as i32) }
    }

    pub fn int64(&self, col: usize) -> i64 {
        unsafe { ffi::sqlite3_column_int64(self.raw, col as i32) }
    }

    pub fn real(&self, col: usize) -> f64 {
        unsafe { ffi::sqlite3_column_double(self.raw, col as i32) }
    }

    pub fn text(&self, col: usize) -> Result<String> {
        let ptr = unsafe { ffi::sqlite3_column_text(self.raw, col as i32) };
        if ptr.is_null() {
            return Ok(String::new());
        }
        let n = unsafe { ffi::sqlite3_column_bytes(self.raw, col as i32) } as usize;
        let bytes = unsafe { std::slice::from_raw_parts(ptr, n) };
        Ok(String::from_utf8_lossy(bytes).into_owned())
    }

    pub fn blob(&self, col: usize) -> Vec<u8> {
        let ptr = unsafe { ffi::sqlite3_column_blob(self.raw, col as i32) };
        if ptr.is_null() {
            return Vec::new();
        }
        let n = unsafe { ffi::sqlite3_column_bytes(self.raw, col as i32) } as usize;
        let bytes = unsafe { std::slice::from_raw_parts(ptr as *const u8, n) };
        bytes.to_vec()
    }
}

impl Drop for Statement<'_> {
    fn drop(&mut self) {
        if !self.raw.is_null() {
            unsafe { ffi::sqlite3_finalize(self.raw) };
            self.raw = std::ptr::null_mut();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(tag: &str) -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("atlas_driver_{}_{}", tag, std::process::id()));
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn connection_law_is_applied_and_observed() {
        let dir = temp_dir("law");
        let path = dir.join("law.db");
        let _ = std::fs::remove_file(&path);
        let conn = Conn::open(&path).unwrap();
        let law = conn.apply_connection_law().unwrap();
        assert_eq!(law.journal_mode, "wal");
        assert_eq!(law.synchronous, "full");
        assert_eq!(law.foreign_keys, "1");
        assert_eq!(law.busy_timeout_ms, 5000);
        drop(conn);
        // A WAL-mode DB leaves -wal/-shm siblings while open; after close
        // they may fold away, but the file itself must stand.
        assert!(path.is_file());
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn bind_step_round_trip_all_types() {
        let dir = temp_dir("bind");
        let path = dir.join("bind.db");
        let _ = std::fs::remove_file(&path);
        let conn = Conn::open(&path).unwrap();
        conn.exec("CREATE TABLE t (a INTEGER, b TEXT, c BLOB);").unwrap();
        let ins = conn
            .prepare("INSERT INTO t (a, b, c) VALUES (?, ?, ?);")
            .unwrap();
        ins.bind_int64(1, 42).unwrap();
        ins.bind_text(2, "café €").unwrap();
        ins.bind_blob(3, &[0u8, 1, 2, 255]).unwrap();
        assert!(matches!(ins.step().unwrap(), Step::Done));
        drop(ins);

        let q = conn.prepare("SELECT a, b, c FROM t;").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 42);
        assert_eq!(q.text(1).unwrap(), "café \u{20ac}");
        assert_eq!(q.blob(2), vec![0, 1, 2, 255]);
        assert!(matches!(q.step().unwrap(), Step::Done));
        drop(q);

        // NULL binding and NULL read-back.
        conn.exec("INSERT INTO t (a, b, c) VALUES (7, NULL, NULL);")
            .unwrap();
        let q = conn.prepare("SELECT b, c FROM t WHERE a = 7;").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.column_type(0), ffi::SQLITE_NULL);
        assert_eq!(q.text(0).unwrap(), "");
        assert_eq!(q.blob(1), Vec::<u8>::new());
        drop(q);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn readonly_open_refuses_to_create_and_errors_carry_sqlites_words() {
        let dir = temp_dir("ro");
        let absent = dir.join("never_made.db");
        let _ = std::fs::remove_file(&absent);
        assert!(Conn::open_readonly(&absent).is_err());

        let present = dir.join("real.db");
        let _ = std::fs::remove_file(&present);
        let w = Conn::open(&present).unwrap();
        w.exec("CREATE TABLE r (x TEXT); INSERT INTO r VALUES ('v');").unwrap();
        drop(w);
        let ro = Conn::open_readonly(&present).unwrap();
        let err = ro.exec("INSERT INTO r VALUES ('nope');").unwrap_err();
        assert!(
            err.msg.to_lowercase().contains("readonly")
                || err.msg.to_lowercase().contains("read-only"),
            "{:?}",
            err
        );
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn passive_checkpoint_succeeds_on_a_lawful_db() {
        let dir = temp_dir("ckpt");
        let path = dir.join("ckpt.db");
        let _ = std::fs::remove_file(&path);
        let conn = Conn::open(&path).unwrap();
        conn.apply_connection_law().unwrap();
        conn.exec("CREATE TABLE w (x INTEGER);").unwrap();
        for i in 0..100 {
            conn.exec(&format!("INSERT INTO w VALUES ({i});")).unwrap();
        }
        let (log, ckpt) = conn.wal_checkpoint_passive().unwrap();
        assert!(log >= 0 && ckpt >= 0);
        std::fs::remove_dir_all(&dir).ok();
    }
}

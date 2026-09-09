//! Raw SQLite FFI (THE_CATALOG S-row · SPEC_SQLITE support).
//!
//! Operator ruling 2026-08-25 (Option A): the driver binds the system
//! `winsqlite3.dll` — zero crates.io, zero downloads, zero compiler. The
//! Windows SDK ships the import library (`um\x64\winsqlite3.lib`), so the
//! seam is a plain static `#[link]`; the DLL itself resolves from System32
//! at load time. Spike witnessed 2026-08-25: 26/26 probed symbols present,
//! libversion 3.51.1 (>= the 3.50.4 that wrote data\master.db).

#![allow(non_camel_case_types)]

use std::os::raw::{c_char, c_int, c_void};

pub type Db = *mut c_void;
pub type Stmt = *mut c_void;

pub const SQLITE_OK: c_int = 0;
pub const SQLITE_ROW: c_int = 100;
pub const SQLITE_DONE: c_int = 101;

pub const SQLITE_OPEN_READONLY: c_int = 0x0000_0001;
pub const SQLITE_OPEN_READWRITE: c_int = 0x0000_0002;
pub const SQLITE_OPEN_CREATE: c_int = 0x0000_0004;
pub const SQLITE_OPEN_FULLMUTEX: c_int = 0x0001_0000;

pub const SQLITE_INTEGER: c_int = 1;
pub const SQLITE_FLOAT: c_int = 2;
pub const SQLITE_TEXT: c_int = 3;
pub const SQLITE_BLOB: c_int = 4;
pub const SQLITE_NULL: c_int = 5;

/// SQLITE_TRANSIENT: SQLite copies the bound bytes immediately.
pub const SQLITE_TRANSIENT: isize = -1;

pub const CHECKPOINT_PASSIVE: c_int = 0;

#[link(name = "winsqlite3")]
extern "C" {
    pub fn sqlite3_libversion() -> *const c_char;
    pub fn sqlite3_sourceid() -> *const c_char;
    pub fn sqlite3_open_v2(
        filename: *const c_char,
        pp_db: *mut Db,
        flags: c_int,
        vfs: *const c_char,
    ) -> c_int;
    pub fn sqlite3_close_v2(db: Db) -> c_int;
    pub fn sqlite3_exec(
        db: Db,
        sql: *const c_char,
        callback: Option<unsafe extern "C" fn(*mut c_void, c_int, *mut *mut c_char, *mut *mut c_char) -> c_int>,
        arg: *mut c_void,
        errmsg: *mut *mut c_char,
    ) -> c_int;
    pub fn sqlite3_prepare_v2(
        db: Db,
        z_sql: *const c_char,
        n_byte: c_int,
        pp_stmt: *mut Stmt,
        pz_tail: *mut *const c_char,
    ) -> c_int;
    pub fn sqlite3_step(stmt: Stmt) -> c_int;
    pub fn sqlite3_reset(stmt: Stmt) -> c_int;
    pub fn sqlite3_clear_bindings(stmt: Stmt) -> c_int;
    pub fn sqlite3_finalize(stmt: Stmt) -> c_int;
    pub fn sqlite3_bind_int64(stmt: Stmt, idx: c_int, value: i64) -> c_int;
    pub fn sqlite3_bind_double(stmt: Stmt, idx: c_int, value: f64) -> c_int;
    pub fn sqlite3_bind_text(
        stmt: Stmt,
        idx: c_int,
        value: *const c_char,
        n: c_int,
        destructor: isize,
    ) -> c_int;
    pub fn sqlite3_bind_blob(
        stmt: Stmt,
        idx: c_int,
        value: *const c_void,
        n: c_int,
        destructor: isize,
    ) -> c_int;
    pub fn sqlite3_bind_null(stmt: Stmt, idx: c_int) -> c_int;
    pub fn sqlite3_column_count(stmt: Stmt) -> c_int;
    pub fn sqlite3_column_type(stmt: Stmt, col: c_int) -> c_int;
    pub fn sqlite3_column_int64(stmt: Stmt, col: c_int) -> i64;
    pub fn sqlite3_column_double(stmt: Stmt, col: c_int) -> f64;
    pub fn sqlite3_column_text(stmt: Stmt, col: c_int) -> *const u8;
    pub fn sqlite3_column_bytes(stmt: Stmt, col: c_int) -> c_int;
    pub fn sqlite3_column_blob(stmt: Stmt, col: c_int) -> *const c_void;
    pub fn sqlite3_errmsg16(db: Db) -> *const u16;
    pub fn sqlite3_changes(db: Db) -> c_int;
    pub fn sqlite3_last_insert_rowid(db: Db) -> i64;
    pub fn sqlite3_busy_timeout(db: Db, ms: c_int) -> c_int;
    pub fn sqlite3_wal_checkpoint_v2(
        db: Db,
        z_db: *const c_char,
        mode: c_int,
        log_frames: *mut c_int,
        checkpointed: *mut c_int,
    ) -> c_int;
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CStr;

    #[test]
    fn the_system_dll_answers_through_rust() {
        let ver = unsafe { CStr::from_ptr(sqlite3_libversion()) };
        assert_eq!(ver.to_str().unwrap(), "3.51.1");
        let sid = unsafe { CStr::from_ptr(sqlite3_sourceid()) };
        assert!(sid.to_str().unwrap().len() > 20);
    }

    #[test]
    fn open_close_round_trip_on_temp_ground() {
        let dir = std::env::temp_dir().join(format!("atlas_ffi_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("probe.db");
        let _ = std::fs::remove_file(&path);
        let cpath = std::ffi::CString::new(path.to_str().unwrap()).unwrap();
        let mut db: Db = std::ptr::null_mut();
        let rc = unsafe {
            sqlite3_open_v2(
                cpath.as_ptr(),
                &mut db,
                SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
                std::ptr::null(),
            )
        };
        assert_eq!(rc, SQLITE_OK);
        assert!(!db.is_null());
        unsafe {
            assert_eq!(sqlite3_close_v2(db), SQLITE_OK);
        }
        assert!(path.is_file());
        std::fs::remove_dir_all(&dir).ok();
    }
}

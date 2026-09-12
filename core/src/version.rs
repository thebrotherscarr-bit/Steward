//! Build versioning seam (SPEC_SEAM §Versioning): the root VERSION file is
//! the single authority; every binary answers --version with exactly its
//! trimmed content — plain semver, e.g. `0.1.2`.
//!
//! STONE MONIKERS ARE STRUCK. Through 0.1.1 the version carried a build tag
//! naming the stone that cut it — `0.1.0+a1` through `0.1.1+f1`, one letter
//! per stone (a1 spine, a2 registry, b1 THE LINE, b2 THE MESH, c1 faces,
//! d1 town, d2 trade+door, e1 kernels, f1 harvest). The operator struck them
//! 2026-09-10: "remove the moniker for the stones, no letters in my
//! versions." The stones are still named in THE_ROAD.md and the CHANGELOG's
//! released entries, which are the record of what happened; the version is
//! now only what the thing IS. The tests below REFUSE a tag rather than
//! require one, so the moniker cannot creep back in unnoticed.

pub const VERSION_FILE: &str = include_str!("../../VERSION");

pub fn atlas_version() -> &'static str {
    VERSION_FILE.trim()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_is_plain_semver() {
        let v = atlas_version();
        let parts: Vec<&str> = v.split('.').collect();
        assert!(
            parts.len() == 3
                && parts
                    .iter()
                    .all(|p| !p.is_empty() && p.chars().all(|c| c.is_ascii_digit())),
            "VERSION must be three numbers and two dots, got {v:?}"
        );
    }

    #[test]
    fn no_stone_tag_and_no_whitespace() {
        let v = atlas_version();
        assert!(
            !v.contains('+'),
            "the stone moniker was struck 2026-09-10; got {v:?}"
        );
        assert!(
            !v.chars().any(char::is_whitespace),
            "VERSION carries embedded whitespace: {v:?}"
        );
        assert_eq!(v, "0.1.5");
    }
}

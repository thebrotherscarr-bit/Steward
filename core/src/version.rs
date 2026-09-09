//! Build versioning seam (SPEC_SEAM §Versioning): the root VERSION file is
//! the single authority; every binary answers --version with exactly its
//! trimmed content (semver + stone tag, e.g. `0.1.0+a1`).

pub const VERSION_FILE: &str = include_str!("../../VERSION");

pub fn atlas_version() -> &'static str {
    VERSION_FILE.trim()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_carries_semver_and_stone() {
        let v = atlas_version();
        assert!(
            v.starts_with("0.1.") && v.contains('+') && !v.ends_with('+'),
            "VERSION must be semver+stone, got {v:?}"
        );
    }

    #[test]
    fn no_whitespace_embedded() {
        // Pinned per stone: a1 (sittings 1-4) · a2 rode a1 by oversight,
        // paid at B1 opening 2026-08-25 · b1 from THE LINE · b2 THE MESH
        // (spec-first implementation opening 2026-08-27) · c1 FACES
        // (sitting 15: console-v2 + bridge + atl) · d1 TOWN (sitting 16:
        // atlas-town beat/flow/story/look/prove) · d2 TRADE+DOOR (sitting 17:
        // trade books parity + atlas-door badge/forms) · e1 KERNELS
        // (sittings 18-19: libppmi + digest/foldall + predictor bench) ·
        // f1 HARVEST (sittings 20-25: rack trio + envelopes + guard +
        // skill lint, all small on loopback Ollama).
        assert_eq!(atlas_version(), "0.1.1+f1");
    }
}

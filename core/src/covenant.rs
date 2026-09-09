//! Identity derivation, two epochs (THE_CATALOG R9 · SPEC_COVENANT).
//! Construction A over the declared doc order; House default
//! (`151274…5bbb`, five docs), Elder legacy-only behind an explicit epoch
//! (`65118a…9dd9`, four docs); intruder files move nothing; a flipped byte
//! names its doc (A1-07a/b).
pub mod golden {
    //! Expected covenants, verbatim from SPEC_COVENANT.
    pub const HOUSE_COVENANT: &str = "1512741580b7239b80c53e2456b46aa9ec43586788d569da0895718dccf15bbb";
    pub const ELDER_COVENANT: &str = "65118a147dd49ed96068e8a3cf1a472db1f4d91253b23507c56926ba2d8d9dd9";
}

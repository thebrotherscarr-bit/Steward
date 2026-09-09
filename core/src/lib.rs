//! atlas-core — the provenance heart (SPEC_SEAM: every hash, canon,
//! signature, and seal verification is computed in exactly one place).
//!
//! Stones: A1 lands sha256, canon, forms, chain, covenant, us; later stones
//! add schnorr/keys, fold, merkle_dag, blanks, vault (THE_CATALOG R-rows).
pub mod blanks;
pub mod canon;
pub mod chain;
pub mod covenant;
pub mod fold;
pub mod forms;
pub mod json;
pub mod keys;
pub mod merkle;
pub mod merkle_dag;
pub mod pyjson;
pub mod schnorr;
pub mod sha256;
pub mod us;
pub mod vault;
pub mod version;

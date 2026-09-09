//! Merkle trees over link hashes (THE_CATALOG R-row · SPEC_CHAINS §wraps).
//!
//! Exact port of the oracle (`estate/Neiro/lib/us_chain.py`): RFC 9162's
//! domain separation (leaf prefix 0x00, node prefix 0x01) but NOT its tree
//! shape — an odd node is CARRIED UP, never doubled. An absent `mv` marker
//! in a wrap reads as v1 forever: roots already closed under v1 must not be
//! recomputed under v2 and called tampered.

use crate::json::Json;
use crate::sha256;

pub const MERKLE_V: u8 = 2;
pub const GENESIS: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";

fn hex32(s: &str) -> Option<[u8; 32]> {
    if s.len() != 64 {
        return None;
    }
    let mut out = [0u8; 32];
    for (i, pair) in s.as_bytes().chunks(2).enumerate() {
        let hi = (pair[0] as char).to_digit(16)?;
        let lo = (pair[1] as char).to_digit(16)?;
        out[i] = ((hi << 4) | lo) as u8;
    }
    Some(out)
}

fn leaf(hexhash: &str, mv: u8) -> String {
    if mv == 1 {
        return hexhash.to_string(); // v1 did not separate the domains
    }
    let bytes = hex32(hexhash)
        .unwrap_or_else(|| panic!("leaf hash {} is not 64 hex", hexhash));
    let mut material = vec![0u8];
    material.extend_from_slice(&bytes);
    sha256::hex_digest(&material)
}

fn node(left: &str, right: &str, mv: u8) -> String {
    if mv == 1 {
        let mut material = hex32(left)
            .unwrap_or_else(|| panic!("node hash {} is not 64 hex", left)).to_vec();
        material.extend_from_slice(
            &hex32(right)
                .unwrap_or_else(|| panic!("node hash {} is not 64 hex", right)),
        );
        return sha256::hex_digest(&material);
    }
    let mut material = vec![1u8];
    material.extend_from_slice(&hex32(left).expect("left leaf hex"));
    material.extend_from_slice(&hex32(right).expect("right leaf hex"));
    sha256::hex_digest(&material)
}

/// Root over entry hashes. An odd node is carried up, never doubled —
/// doubling lets one leaf stand in for two, which is a real attack.
pub fn merkle(leaf_hashes: &[String], mv: u8) -> String {
    if leaf_hashes.is_empty() {
        return GENESIS.to_string();
    }
    let mut level: Vec<String> = leaf_hashes.iter().map(|h| leaf(h, mv)).collect();
    while level.len() > 1 {
        let mut next: Vec<String> = Vec::with_capacity(level.len() / 2 + 1);
        let mut i = 0;
        while i + 1 < level.len() {
            next.push(node(&level[i], &level[i + 1], mv));
            i += 2;
        }
        if level.len() % 2 == 1 {
            next.push(level[level.len() - 1].clone()); // carried, not doubled
        }
        level = next;
    }
    level[0].clone()
}

/// The siblings needed to climb from one leaf to the root.
/// Each step names the sibling side from the climber's view:
/// ('R', sib) means the missing piece sits on the right.
pub fn merkle_path(leaf_hashes: &[String], index: usize, mv: u8) -> Vec<(char, String)> {
    let mut level: Vec<String> = leaf_hashes.iter().map(|h| leaf(h, mv)).collect();
    let mut path = Vec::new();
    let mut i = index;
    while level.len() > 1 {
        let mut next: Vec<String> = Vec::new();
        let mut j = 0;
        while j + 1 < level.len() {
            if j == i {
                path.push(('R', level[j + 1].clone()));
            } else if j + 1 == i {
                path.push(('L', level[j].clone()));
            }
            next.push(node(&level[j], &level[j + 1], mv));
            j += 2;
        }
        let carried = level.len() % 2 == 1;
        if carried {
            next.push(level[level.len() - 1].clone());
        }
        if carried && i == level.len() - 1 {
            i = next.len() - 1; // rode up untouched
        } else {
            i /= 2;
        }
        level = next;
    }
    path
}

/// Walk a path from a leaf to the root. A stranger with the root and this
/// path proves the leaf belongs, needing nothing else.
pub fn climb(leaf_hash: &str, path: &[(char, String)], mv: u8) -> String {
    let mut cur = leaf(leaf_hash, mv);
    for (side, sib) in path {
        cur = if *side == 'R' {
            node(&cur, sib, mv)
        } else {
            node(sib, &cur, mv)
        };
    }
    cur
}

/// Which tree a wrap was built with. An ABSENT marker means v1, and stays
/// verifiable as one forever.
pub fn wrap_version(wrap_entry: &Json) -> u8 {
    match wrap_entry
        .get("payload")
        .and_then(|p| p.get("mv"))
    {
        Some(Json::Int(v)) => *v as u8,
        _ => 1,
    }
}

// -- the third dialect: forge/links v1, the library's original tree ----------
//
// The estate's own writers disagree about what "v1" means. us_chain's v1
// concatenates BYTES-FROM-HEX at each node; forge/links/links.py (which wrote
// every Jesster library wrap) concatenated the HEX TEXT ITSELF through its
// _h() helper and never pre-hashed leaves. Eight closed roots across gen2/
// gen3/gen4 pin that reading. Fold law: named, kept verifiable, never merged.

/// forge/links v1: sha256 over the UTF-8 hex-text concatenation; odd node
/// carried, never doubled.
pub fn merkle_links_v1(leaf_hashes: &[String]) -> String {
    if leaf_hashes.is_empty() {
        return GENESIS.to_string();
    }
    let mut row: Vec<String> = leaf_hashes.to_vec();
    while row.len() > 1 {
        let mut next = Vec::with_capacity(row.len() / 2 + 1);
        let mut i = 0;
        while i + 1 < row.len() {
            next.push(sha256::hex_digest(
                format!("{}{}", row[i], row[i + 1]).as_bytes(),
            ));
            i += 2;
        }
        if row.len() % 2 == 1 {
            next.push(row[row.len() - 1].clone());
        }
        row = next;
    }
    row[0].clone()
}

/// forge/links v1 sibling path (raw hex strings; same shape rules).
pub fn merkle_path_links_v1(leaf_hashes: &[String], index: usize) -> Vec<(char, String)> {
    let mut row: Vec<String> = leaf_hashes.to_vec();
    let mut path = Vec::new();
    let mut i = index;
    while row.len() > 1 {
        let mut next = Vec::new();
        let mut j = 0;
        while j + 1 < row.len() {
            if j == i {
                path.push(('R', row[j + 1].clone()));
            } else if j + 1 == i {
                path.push(('L', row[j].clone()));
            }
            next.push(sha256::hex_digest(
                format!("{}{}", row[j], row[j + 1]).as_bytes(),
            ));
            j += 2;
        }
        let carried = row.len() % 2 == 1;
        if carried {
            next.push(row[row.len() - 1].clone());
        }
        if carried && i == row.len() - 1 {
            i = next.len() - 1;
        } else {
            i /= 2;
        }
        row = next;
    }
    path
}

/// Walk a forge/links v1 path from a leaf to its root.
pub fn climb_links_v1(leaf_hash: &str, path: &[(char, String)]) -> String {
    let mut cur = leaf_hash.to_string();
    for (side, sib) in path {
        cur = if *side == 'R' {
            sha256::hex_digest(format!("{}{}", cur, sib).as_bytes())
        } else {
            sha256::hex_digest(format!("{}{}", sib, cur).as_bytes())
        };
    }
    cur
}

/// The named trees a root may have closed under.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tree {
    /// forge/links text-concat tree (absent-mv Jesster lineage).
    LinksV1Text,
    /// us_chain's binary-concat v1.
    UsChainV1Binary,
    /// RFC 9162 domain-separated (stamped mv=2).
    DomainSeparatedV2,
}

impl Tree {
    pub fn name(&self) -> &'static str {
        match self {
            Tree::LinksV1Text => "links-v1 text",
            Tree::UsChainV1Binary => "us-chain v1 binary",
            Tree::DomainSeparatedV2 => "domain-separated v2",
        }
    }
}

/// Recognition-by-trial for one wrap root, honoring the versioning law:
/// an mv=2 stamp is verified ONLY under the separated tree (recomputing a
/// stamped root elsewhere and calling it tampered is forbidden); an absent
/// or mv=1 stamp tries the two historical v1 dialects and names which one
/// reproduces. Refuses with every mismatch named when none do.
pub fn verify_wrap_root(
    leaf_hashes: &[String],
    recorded_root: &str,
    stamped_mv: Option<u8>,
) -> Result<(Tree, String), String> {
    match stamped_mv {
        Some(2) => {
            let got = merkle(leaf_hashes, 2);
            if got == recorded_root {
                Ok((Tree::DomainSeparatedV2, got))
            } else {
                Err(format!(
                    "wrap stamped mv=2 does not reproduce under the separated tree: \
                     computed {} != recorded {}",
                    got, recorded_root
                ))
            }
        }
        _ => {
            let a = merkle_links_v1(leaf_hashes);
            if a == recorded_root {
                return Ok((Tree::LinksV1Text, a));
            }
            let b = merkle(leaf_hashes, 1);
            if b == recorded_root {
                return Ok((Tree::UsChainV1Binary, b));
            }
            Err(format!(
                "no known tree reproduces the root: links-v1-text={}, \
                 us-chain-v1-binary={} vs recorded {}",
                a, b, recorded_root
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn leaves(n: usize) -> Vec<String> {
        // Distinct deterministic 64-hex "link hashes".
        (0..n)
            .map(|i| sha256::hex_digest(format!("leaf-{}", i).as_bytes()))
            .collect()
    }

    #[test]
    fn empty_ground_roots_at_genesis_and_single_leaf_folds_to_its_leaf() {
        assert_eq!(merkle(&[], MERKLE_V), GENESIS);
        let one = leaves(1);
        assert_eq!(merkle(&one, MERKLE_V), leaf(&one[0], MERKLE_V));
    }

    #[test]
    fn domain_separation_changes_the_tree_v1_is_not_v2() {
        let ls = leaves(40);
        assert_ne!(merkle(&ls, 1), merkle(&ls, 2));
    }

    #[test]
    fn an_odd_node_is_carried_up_not_doubled() {
        let three = leaves(3);
        let carried = merkle(&three, MERKLE_V);
        let doubled = node(
            &node(&leaf(&three[0], MERKLE_V), &leaf(&three[1], MERKLE_V), MERKLE_V),
            &node(&leaf(&three[2], MERKLE_V), &leaf(&three[2], MERKLE_V), MERKLE_V),
            MERKLE_V,
        );
        assert_ne!(carried, doubled);
    }

    #[test]
    fn every_leaf_climbs_to_the_same_root_across_shapes() {
        for n in [1usize, 2, 3, 5, 7, 40, 41] {
            let ls = leaves(n);
            let root = merkle(&ls, MERKLE_V);
            for i in 0..n {
                let path = merkle_path(&ls, i, MERKLE_V);
                assert_eq!(
                    climb(&ls[i], &path, MERKLE_V),
                    root,
                    "n={} leaf={}",
                    n,
                    i
                );
            }
        }
    }

    #[test]
    fn a_stranger_with_root_and_path_proves_membership_without_the_rest() {
        let ls = leaves(40);
        let root = merkle(&ls, MERKLE_V);
        let idx = 37;
        let path = merkle_path(&ls, idx, MERKLE_V);
        assert_eq!(climb(&ls[idx], &path, MERKLE_V), root);
        // A wrong leaf cannot climb to the same root.
        assert_ne!(climb(&leaves(99)[0], &path, MERKLE_V), root);
    }

    #[test]
    fn an_absent_mv_marker_reads_as_v1_forever() {
        let wrap = Json::Obj(vec![(
            "payload".into(),
            Json::Obj(vec![]),
        )]);
        assert_eq!(wrap_version(&wrap), 1);
        let stamped = Json::Obj(vec![(
            "payload".into(),
            Json::Obj(vec![("mv".into(), Json::Int(2))]),
        )]);
        assert_eq!(wrap_version(&stamped), 2);
    }
}

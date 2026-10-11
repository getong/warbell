//! Tiny scoped data-parallel map for the world build (no rayon dependency). The build's heavy CPU
//! work — terrain-chunk meshing, the tile classification bake, chunk mesh merges — is a list of
//! independent pure jobs; [`par_map`] runs them across the cores and returns the results IN INPUT
//! ORDER, so everything downstream (entity spawn order, RNG-free placement) stays deterministic.

use std::sync::atomic::{AtomicUsize, Ordering};

/// Worker count: the machine's parallelism, capped (the build also shares the CPU with the
/// render thread and asset loaders).
fn workers() -> usize {
    std::thread::available_parallelism().map_or(4, |n| n.get()).clamp(1, 16)
}

/// `(0..n).map(f).collect()`, evaluated on scoped worker threads. Jobs are pulled one at a time
/// from a shared counter, so uneven job sizes (an empty sea chunk vs a cliff-heavy one) balance.
pub fn par_map<T: Send, F: Fn(usize) -> T + Sync>(n: usize, f: F) -> Vec<T> {
    let threads = workers().min(n);
    if threads <= 1 {
        return (0..n).map(f).collect();
    }
    let next = AtomicUsize::new(0);
    let mut parts: Vec<Vec<(usize, T)>> = std::thread::scope(|s| {
        let handles: Vec<_> = (0..threads)
            .map(|_| {
                s.spawn(|| {
                    let mut out = Vec::new();
                    loop {
                        let i = next.fetch_add(1, Ordering::Relaxed);
                        if i >= n {
                            break;
                        }
                        out.push((i, f(i)));
                    }
                    out
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join().expect("par_map worker panicked")).collect()
    });
    let mut slots: Vec<Option<T>> = (0..n).map(|_| None).collect();
    for part in parts.drain(..) {
        for (i, v) in part {
            slots[i] = Some(v);
        }
    }
    slots.into_iter().map(|v| v.expect("par_map: every index produced")).collect()
}

#[cfg(test)]
mod tests {
    #[test]
    fn par_map_keeps_order() {
        let v = super::par_map(1000, |i| i * 3);
        assert_eq!(v, (0..1000).map(|i| i * 3).collect::<Vec<_>>());
        assert!(super::par_map(0, |i| i).is_empty());
    }
}

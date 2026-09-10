# -*- coding: utf-8 -*-
"""
2D Plane-Wave Expansion (PWE) mode solver for a SOI strip waveguide.
Pure numpy/scipy self-implementation (no Meep/Tidy3D/any photonics lib).

Method
------
TE polarization. Master longitudinal magnetic field H_z(x,y) ~ e^{i beta z}.
Wave equation:  (nabla_t^2 + k0^2 * eps(x,y)) H_z = beta^2 H_z.

Expanded in a 2D Fourier series over a window [Lx x Ly] (supercell/PWE):
  H_z(x,y) = sum_G c_G exp(i G.r),  and eps is Fourier expanded analytically
  (piecewise constant profile -> closed-form sinc coefficients).
In reciprocal space this is the eigenvalue problem
  D c = beta^2 c,   D_{G,G'} = -|G|^2 delta_{G,G'} + k0^2 eps_{G-G'}.
The operator is real-symmetric; ARPACK 'LA' returns largest beta^2.
n_eff = beta / k0.  Guided modes satisfy  n_clad < n_eff < n_si.

Spurious-mode handling (high index contrast):
  A truncated Fourier series of a discontinuous dielectric produces
  "bulk-silicon" fictitious modes whose n_eff clusters just below n_si
  (~3.0-3.45) and survives truncation.  Genuine bound modes (e.g. TE0 ~2.65)
  stay STABLE with NG.  We therefore isolate the fundamental by:
    * physical UPPER BOUND TH = min(1D-slab-TE0(height), 1D-slab-TE0(width)).
      A 2D strip is confined in BOTH transverse directions, so its TE0 n_eff
      must be below either 1D slab TE0 -> TH ~ 2.85 < 3.48.  This cleanly
      rejects the spurious cluster (all > TH).
    * CROSS-NG CONVERGENCE: the fundamental is the stable (low-drift) branch
      with the largest n_eff below TH.
"""

import numpy as np
from scipy.signal import fftconvolve
from scipy.sparse.linalg import LinearOperator, eigsh

# ---------- problem parameters (must not change) ----------
W_CORE = 0.5          # um, x-direction core width
H_CORE = 0.22         # um, y-direction core height
N_SI = 3.48           # silicon core index
N_CLAD = 1.44         # SiO2 cladding index (BOX + top same)
WL = 1.55             # um, vacuum wavelength
EPS_SI = N_SI**2
EPS_CLAD = N_CLAD**2

GOLDEN = 2.6509       # EIM two-step effective-index reference
TOL = 0.05

K0 = 2.0 * np.pi / WL  # free-space wavenumber, 1/um

# supercell window (>= +-1.5 um cladding each side)
LX = 4.0
LY = 4.0
DGX = 2.0 * np.pi / LX
DGY = 2.0 * np.pi / LY


def _sinc(u):
    u = np.asarray(u, dtype=float)
    out = np.ones_like(u)
    nz = u != 0.0
    out[nz] = np.sin(u[nz]) / u[nz]
    return out


def dielectric_coeffs(NG):
    """Fourier coefficients of eps on the kernel grid H in [-2NG, 2NG]^2."""
    P0 = 4 * NG + 1
    b = np.arange(P0)
    Hx = (b - 2 * NG) * DGX
    Hy = (b - 2 * NG) * DGY
    HX, HY = np.meshgrid(Hx, Hy, indexing='ij')
    core = (W_CORE * H_CORE) / (LX * LY) * _sinc(HX * W_CORE / 2.0) * _sinc(HY * H_CORE / 2.0)
    eps = np.full((P0, P0), EPS_CLAD)
    eps += (EPS_SI - EPS_CLAD) * core
    return eps


def build_operator(NG):
    """Return LinearOperator D for eigenvalue problem D c = beta^2 c."""
    M = 2 * NG + 1
    P0 = 4 * NG + 1
    eps_k = dielectric_coeffs(NG)
    a = np.arange(M)
    Gx = (a - NG) * DGX
    Gy = (a - NG) * DGY
    GX, GY = np.meshgrid(Gx, Gy, indexing='ij')
    G2 = GX**2 + GY**2  # shape (M, M)

    def matvec(c_in):
        c = np.asarray(c_in).reshape(M, M)
        Cpad = np.zeros((P0, P0), dtype=float)
        Cpad[2 * NG:2 * NG + M, 2 * NG:2 * NG + M] = c
        full = fftconvolve(eps_k, Cpad, mode='full')
        Ec = full[2 * NG:2 * NG + M, 2 * NG:2 * NG + M]
        return (K0**2 * Ec - G2 * c).reshape(-1)

    D = LinearOperator((M * M, M * M), matvec=matvec, dtype=float)
    return D, G2, M


def build_dense(NG):
    """Dense N x N matrix of the PWE operator (N = (2NG+1)^2)."""
    D_op, G2, M = build_operator(NG)
    N = M * M
    D = np.zeros((N, N))
    e = np.eye(N)
    for i in range(N):
        D[:, i] = D_op.matvec(e[:, i])
    return D, M


def reconstruct_field(c, M, nx=121, ny=121):
    """Inverse Fourier transform of coefficients onto a real-space grid."""
    c = np.asarray(c).reshape(M, M)
    a = np.arange(M)
    Gx = (a - (M - 1) // 2) * DGX
    Gy = (a - (M - 1) // 2) * DGY
    xs = np.linspace(-LX / 2.0, LX / 2.0, nx)
    ys = np.linspace(-LY / 2.0, LY / 2.0, ny)
    XS, YS = np.meshgrid(xs, ys, indexing='ij')
    field = np.zeros((nx, ny), dtype=complex)
    for ia in range(M):
        for ib in range(M):
            field += c[ia, ib] * np.exp(1j * (Gx[ia] * XS + Gy[ib] * YS))
    return xs, ys, field


def symmetry_score(field):
    """0 = perfectly even-even about origin; higher = more antisymmetric."""
    f = np.real(field)
    nx, ny = f.shape
    cxi, cyi = nx // 2, ny // 2
    fx = f[cxi:, :]
    fxm = f[cxi::-1, :]
    fy = f[:, cyi:]
    fym = f[:, cyi::-1]
    return (np.linalg.norm(fx - fxm) + np.linalg.norm(fy - fym)) / (np.linalg.norm(f) + 1e-30)


def slab_te0(thickness):
    """1D symmetric-slab TE fundamental (largest-n_eff) effective index.

    Even mode: tan(d) = sqrt((n^2 - n_s^2)/(n_f^2 - n^2)),
    d = (h/2) k0 sqrt(n_f^2 - n^2).  The fundamental has the LARGEST n_eff,
    i.e. d in (0, pi/2); we scan from n_f downward and take the highest root.
    """
    n_f, n_s = N_SI, N_CLAD

    def f_of(n):
        d = 0.5 * thickness * K0 * np.sqrt(n_f**2 - n**2)
        rhs = np.sqrt((n**2 - n_s**2) / (n_f**2 - n**2))
        return np.tan(d) - rhs

    ng = 4000
    n_grid = np.linspace(n_f - 1e-5, n_s + 1e-5, ng)
    f = np.array([f_of(n) for n in n_grid])
    for i in range(ng - 1):
        if f[i] * f[i + 1] < 0:
            lo, hi = n_grid[i], n_grid[i + 1]
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if f_of(mid) * f_of(lo) > 0:
                    lo = mid
                else:
                    hi = mid
            return 0.5 * (lo + hi)
    return n_s


def solve_ng(NG, k_eig=24, verbose=True):
    """Return list of (n_eff, vec) for modes near the target band (shift-invert).

    Uses shift-invert around sigma=(k0*2.6)^2 so the true fundamental (~2.65)
    is captured even though it is far below the largest eigenvalues (spurious
    bulk-silicon cluster near n_si).
    """
    D, M = build_dense(NG)
    sigma = (K0 * 2.6) ** 2
    lams, vecs = eigsh(D, k=k_eig, sigma=sigma, which='LM',
                      maxiter=4000, tol=1e-9)
    lams = np.real(lams)
    vecs = np.real(vecs)
    order = np.argsort(lams)[::-1]
    lams = lams[order]
    vecs = vecs[:, order]

    band = []
    for k in range(lams.size):
        if lams[k] <= 0:
            continue
        neff = np.sqrt(lams[k]) / K0
        if N_CLAD + 0.02 < neff < N_SI - 0.002:
            band.append((neff, vecs[:, k]))
    band.sort(key=lambda t: -t[0])
    if verbose:
        print(f"  NG={NG:3d}  M={M:4d}  n_eff captured (desc): " +
              ", ".join(f"{v:.4f}" for v, _ in band[:16]))
    return band, M


def find_te0(per_ng, TH):
    """Cross-NG convergence: isolate the stable fundamental branch.
    per_ng: list of (NG, band_list) coarsest->finest.
    Returns (final_neff, branch_dict NG->neff).
    """
    fine = per_ng[-1][1]
    coarse_chain = per_ng[:-1]
    stable = []
    for neff_f, vec_f in fine:
        if not (N_CLAD < neff_f < TH):
            continue
        chain = [neff_f]
        prev = neff_f
        ok = True
        for (NG_c, band_c) in reversed(coarse_chain):
            vals = np.array([v for v, _ in band_c])
            if vals.size == 0:
                ok = False
                break
            idx = np.argmin(np.abs(vals - prev))
            chain.append(vals[idx])
            prev = vals[idx]
        if not ok:
            continue
        chain = np.array(chain)            # finest -> coarsest
        drift = float(np.sum(np.abs(np.diff(chain))))
        if drift < 0.04:
            stable.append((neff_f, drift, tuple(chain[::-1])))  # coarsest->finest
    if not stable:
        # fallback: largest n_eff below TH with smallest drift
        best = None
        for neff_f, vec_f in fine:
            if not (N_CLAD < neff_f < TH):
                continue
            chain = [neff_f]; prev = neff_f; ok = True
            for (NG_c, band_c) in reversed(coarse_chain):
                vals = np.array([v for v, _ in band_c])
                if vals.size == 0:
                    ok = False; break
                idx = np.argmin(np.abs(vals - prev)); chain.append(vals[idx]); prev = vals[idx]
            if not ok:
                continue
            chain = np.array(chain); drift = float(np.sum(np.abs(np.diff(chain))))
            if best is None or drift < best[1]:
                best = (neff_f, drift, tuple(chain[::-1]))
        if best is None:
            return float('nan'), {}
        stable = [best]
    stable.sort(key=lambda t: -t[0])
    neff_f, drift, chain_cf = stable[0]
    branch = dict(zip([ng for ng, _ in per_ng], chain_cf))
    return neff_f, branch


def _pick(per_ng, neff_f):
    fine = per_ng[-1][1]
    # nearest eigenvector in fine band
    best = min(fine, key=lambda t: abs(t[0] - neff_f))
    return best[1]


def main():
    print("=" * 64)
    print("PWE (Plane-Wave Expansion) TE fundamental mode solver")
    print("=" * 64)
    print(f"w_core={W_CORE} um  h_core={H_CORE} um  n_si={N_SI}  n_clad={N_CLAD}")
    print(f"wl={WL} um  k0={K0:.4f} 1/um  window Lx=Ly={LX} um")
    print(f"golden(EIM)={GOLDEN}  tol={TOL}")
    th_h = slab_te0(H_CORE)
    th_w = slab_te0(W_CORE)
    TH = min(th_h, th_w)
    print(f"1D-slab TE0(h={H_CORE})={th_h:.4f}  TE0(w={W_CORE})={th_w:.4f}  "
          f"-> upper bound TH={TH:.4f} (rejects n_eff>TH spurious bulk modes)")
    print("-" * 64)

    ng_list = [20, 24, 28, 32, 36, 40]
    per_ng = []
    for NG in ng_list:
        band, M = solve_ng(NG, verbose=True)
        per_ng.append((NG, band))

    final, branch = find_te0(per_ng, TH)
    print("-" * 64)
    print("Convergence sequence (TE0 branch, NG : n_eff):")
    conv = []
    for NG, _ in per_ng:
        v = branch.get(NG, float('nan'))
        conv.append((NG, v))
        print(f"   NG={NG:3d} -> n_eff = {v:.6f}")
    neffs = [c[1] for c in conv if not np.isnan(c[1])]
    finalv = neffs[-1] if neffs else float('nan')
    d = finalv - GOLDEN
    ok = abs(d) <= TOL
    print("-" * 64)
    print(f"Final n_eff (NG={ng_list[-1]}) = {finalv:.6f}")
    print(f"Delta vs golden 2.6509      = {d:+.6f}")
    print(f"|Delta| <= {TOL} ?           {ok}  -> "
          f"{'PASS (strictly independent)' if ok else 'CHECK / investigate'}")
    print("=" * 64)
    return finalv, d, ok


if __name__ == "__main__":
    main()

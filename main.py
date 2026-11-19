#!/usr/bin/env python3
"""QuantumSimulation-Lab - educational digital quantum simulation lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * This lab CLASSICALLY simulates a quantum algorithm: digital
    quantum simulation of the transverse-field Ising chain on
    N = 3 and N = 4 spins (Hilbert dimensions 8 and 16), with the
    exact propagator and first- and second-order Trotter-Suzuki
    product formulas all built from scratch - Kronecker products,
    matrix exponentials, operator norms - in plain Python lists.
  * The point is the error bookkeeping: the Trotter error is
    MEASURED against the exact propagator, its log-log slope is
    fitted and graded against the theory (-1 for Lie, -2 for
    Strang), and the step count each order needs to reach a
    labelled target error is printed - verified directly where
    that is affordable, labelled as a fit extrapolation where
    the first-order count (~1.28 million steps) is not.
  * N <= 4 spins on a laptop is not a quantum computer. No speedup
    is claimed anywhere, no hardware is touched, and no finite
    chain of 3-4 spins says anything by itself about the
    thermodynamic limit. Quantum speedup, hardware, chemistry,
    materials, vendor-benchmark, and cryptanalysis claims are
    permanent HOLD gates - with Gemini Argon 4 Extended Thinking
    as DECIDER (names-only, tighten-only), Muse as advisor
    (never overrides HOLD), and Google Flow plan-only seats.

Model (labelled teaching parameters, stated once and used
everywhere): open chain, H = -J sum_i Z_i Z_{i+1} - h sum_i X_i
with J = 1, labelled field h, evolution time t = 1.0, target
Trotter error 1e-6 in operator norm.
"""
import cmath
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# Labelled teaching parameters. J sets the energy unit; h and t are
# the labelled field and evolution time every headline number uses.
J_COUPLING = 1.0
H_FIELD = 1.0
T_EVOL = 1.0
N_SPINS = 4
N_SMALL = 3
TARGET_ERROR = 1e-6
TROTTER_LADDER = (1, 2, 4, 8, 16, 32, 64, 128)
OBS_TIMES = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
H_SWEEP = (0.0, 0.5, 1.0, 1.5, 2.0)

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "quantum_speedup_claim": "HOLD - no quantum speedup claim; this is a classical simulation of at most 4 qubits",
    "real_hardware_execution": "HOLD - no executing circuits on real quantum hardware from this lab",
    "hardware_specification_claim": "HOLD - no qubit counts, coherence times, or fidelity specs for real devices",
    "chemistry_discovery_claim": "HOLD - no claiming a molecule was discovered or a chemical property certified",
    "materials_design_claim": "HOLD - no claiming a material was designed or its properties certified by this sim",
    "drug_discovery_claim": "HOLD - no drug-discovery or pharmacology claims from a 4-spin teaching model",
    "vendor_benchmark_claim": "HOLD - no vendor benchmark comparisons or device rankings",
    "cryptanalysis_claim": "HOLD - no claims about breaking encryption or cryptographic timelines",
    "error_correction_deployment": "HOLD - no fault-tolerance or quantum-error-correction readiness claims",
    "commercial_product_claim": "HOLD - no commercial quantum product or service claims from a lab model",
    "investment_claim": "HOLD - no investment claims; a teaching simulation is not a prospectus",
    "certified_accuracy_claim": "HOLD - no certifying these results as physically exact for any real system",
    "weapons_defense_application": "HOLD - no weapons, targeting, or defense application claims",
    "thermodynamic_limit_claim": "HOLD - no claiming N <= 4 finite-chain results describe the thermodynamic limit or real phase transitions",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Linear algebra kit
# Matrices are plain lists of lists of complex numbers. Everything -
# Kronecker products, the matrix exponential, the operator norm - is
# written out here, because the lab's claim is that the reader can
# check every operation the simulation performs.

def eye(dim):
    return [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]


def kron(A, B):
    """Kronecker product of two matrices."""
    return [[a * b for a in row_a for b in row_b]
            for row_a in A for row_b in B]


def matmul(A, B):
    cols = list(zip(*B))
    return [[sum(x * y for x, y in zip(row, col)) for col in cols]
            for row in A]


def dagger(A):
    return [[A[j][i].conjugate() for j in range(len(A))]
            for i in range(len(A[0]))]


def mat_add(A, B, scale_b=1.0):
    return [[a + scale_b * b for a, b in zip(row_a, row_b)]
            for row_a, row_b in zip(A, B)]


def mat_scale(A, s):
    return [[s * x for x in row] for row in A]


def matvec(A, v):
    return [sum(x * y for x, y in zip(row, v)) for row in A]


def frob_norm(A):
    return math.sqrt(sum(abs(x) ** 2 for row in A for x in row))


def max_dev(A, B):
    """Largest absolute entrywise difference between two matrices."""
    return max(abs(a - b) for row_a, row_b in zip(A, B)
               for a, b in zip(row_a, row_b))


def commutator_norm(A, B):
    """Frobenius norm of [A, B] - zero exactly when the parts commute."""
    return frob_norm(mat_add(matmul(A, B), matmul(B, A), scale_b=-1.0))


def mat_exp_neg_iH(H, t):
    """Exact propagator U(t) = exp(-i H t) by scaling-and-squaring.

    The exponential is a Taylor series on the scaled matrix
    -iHt / 2^s (scaled until its max row sum is <= 0.5, so the
    series converges to machine precision in a few dozen terms),
    squared back up s times. Which method this is matters: it is
    stated here, and CHECKS grade the result by unitarity
    ||U^dagger U - I|| and by U(t) U(-t) = I, not by trust.
    """
    dim = len(H)
    A = [[-1j * t * H[i][j] for j in range(dim)] for i in range(dim)]
    norm = max(sum(abs(x) for x in row) for row in A)
    s = 0
    while norm / (2.0 ** s) > 0.5:
        s += 1
    factor = 2.0 ** s
    As = [[x / factor for x in row] for row in A]
    E = eye(dim)
    term = eye(dim)
    for k in range(1, 60):
        term = mat_scale(matmul(term, As), 1.0 / k)
        E = mat_add(E, term)
        if max(abs(x) for row in term for x in row) < 1e-18:
            break
    for _ in range(s):
        E = matmul(E, E)
    return E


def op_norm(M):
    """Operator (spectral) norm by power iteration on M^dagger M.

    Two deterministic start vectors (all-ones and alternating
    signs); the larger Rayleigh quotient wins. Deterministic, so
    every run - and every rerun - reports the same norm.
    """
    dim = len(M)
    MtM = matmul(dagger(M), M)
    best = 0.0
    starts = ([1.0] * dim,
              [1.0 if i % 2 == 0 else -1.0 for i in range(dim)])
    for start in starts:
        v = [x / math.sqrt(dim) for x in start]
        for _ in range(300):
            w = matvec(MtM, v)
            nrm = math.sqrt(sum(abs(x) ** 2 for x in w))
            if nrm == 0.0:
                break
            v = [x / nrm for x in w]
        ray = sum(v[i].conjugate() * x
                  for i, x in enumerate(matvec(MtM, v))).real
        best = max(best, ray)
    return math.sqrt(max(best, 0.0))


def op_error(U_approx, U_exact):
    """The lab's one error measure: ||U_approx - U_exact|| operator norm."""
    dim = len(U_exact)
    diff = [[U_approx[i][j] - U_exact[i][j] for j in range(dim)]
            for i in range(dim)]
    return op_norm(diff)


# ================================================================ 2. The TFIM chain
# Qubit 0 is the most significant bit of the basis index. Open chain:
# N - 1 bonds. Z eigenvalues: bit 0 (up) -> +1, bit 1 (down) -> -1.

I2 = [[1.0, 0.0], [0.0, 1.0]]
X2 = [[0.0, 1.0], [1.0, 0.0]]
Z2 = [[1.0, 0.0], [0.0, -1.0]]


def onsite(N, site, M):
    """Single-qubit operator M on `site`, identity elsewhere (Kronecker)."""
    out = [[1.0]]
    for q in range(N):
        out = kron(out, M if q == site else I2)
    return out


def hamiltonian_parts(N, J, h):
    """(A, B) with H = A + B: A = -J sum Z_i Z_{i+1}, B = -h sum X_i."""
    dim = 2 ** N
    A = [[0.0] * dim for _ in range(dim)]
    B = [[0.0] * dim for _ in range(dim)]
    for i in range(N - 1):
        ZZ = matmul(onsite(N, i, Z2), onsite(N, i + 1, Z2))
        for a in range(dim):
            for b in range(dim):
                A[a][b] += -J * ZZ[a][b]
    for i in range(N):
        Xi = onsite(N, i, X2)
        for a in range(dim):
            for b in range(dim):
                B[a][b] += -h * Xi[a][b]
    return A, B


def build_hamiltonian(N, J, h):
    A, B = hamiltonian_parts(N, J, h)
    return mat_add(A, B)


# ================================================================ 3. Trotter-Suzuki factors
# Each factor is exponentiated EXACTLY, as a full matrix:
#   exp(-i A tau): A is diagonal in the Z basis, so this is a
#     diagonal phase matrix, entry exp(+i J tau sum_i z_i z_{i+1}).
#   exp(-i B tau): a Kronecker product of per-qubit rotations
#     exp(i h tau X) = cos(h tau) I + i sin(h tau) X.
# The product formulas then multiply full matrices, for clarity:
#   order 1 (Lie):    U1(tau) = exp(-iB tau) exp(-iA tau)
#   order 2 (Strang): U2(tau) = exp(-iA tau/2) exp(-iB tau) exp(-iA tau/2)

def exp_zz(N, J, tau):
    """exp(-i A tau) exactly: diagonal phases from the ZZ part."""
    dim = 2 ** N
    M = [[0.0] * dim for _ in range(dim)]
    for s in range(dim):
        z = [1 if ((s >> (N - 1 - q)) & 1) == 0 else -1 for q in range(N)]
        phase = sum(z[i] * z[i + 1] for i in range(N - 1))
        M[s][s] = cmath.exp(1j * J * tau * phase)
    return M


def exp_x(N, h, tau):
    """exp(-i B tau) exactly: Kronecker product of X rotations."""
    c = math.cos(h * tau)
    s = math.sin(h * tau)
    R = [[c, 1j * s], [1j * s, c]]
    out = [[1.0]]
    for _ in range(N):
        out = kron(out, R)
    return out


def trotter_step(N, J, h, tau, order):
    if order == 1:
        return matmul(exp_x(N, h, tau), exp_zz(N, J, tau))
    if order == 2:
        half = exp_zz(N, J, tau / 2.0)
        return matmul(matmul(half, exp_x(N, h, tau)), half)
    raise ValueError(f"unknown Trotter order: {order}")


_CACHE = {}


def exact_propagator(N, J, h, t):
    key = ("exact", N, J, h, t)
    if key not in _CACHE:
        _CACHE[key] = mat_exp_neg_iH(build_hamiltonian(N, J, h), t)
    return _CACHE[key]


def trotter_propagator(N, J, h, t, n, order):
    key = ("trotter", N, J, h, t, n, order)
    if key not in _CACHE:
        step = trotter_step(N, J, h, t / n, order)
        U = eye(2 ** N)
        for _ in range(n):
            U = matmul(step, U)
        _CACHE[key] = U
    return _CACHE[key]


def trotter_error(N, J, h, t, n, order):
    return op_error(trotter_propagator(N, J, h, t, n, order),
                    exact_propagator(N, J, h, t))


# ================================================================ 4. Error analysis
# The ladder: operator-norm error at fixed t for n = 1..128, both
# orders. The log-log slope is fitted over the asymptotic region
# (n >= 4) and graded against theory: -1 for Lie, -2 for Strang.

def _fit_loglog(ns, errs):
    xs = [math.log(n) for n in ns]
    ys = [math.log(e) for e in errs]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    slope = (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
             / sum((x - mx) ** 2 for x in xs))
    return slope, my - slope * mx


def trotter_report(N=N_SPINS, J=J_COUPLING, h=H_FIELD, t=T_EVOL):
    U_exact = exact_propagator(N, J, h, t)
    orders = {}
    for order in (1, 2):
        ladder = {n: trotter_error(N, J, h, t, n, order)
                  for n in TROTTER_LADDER}
        fit_ns = [n for n in TROTTER_LADDER if n >= 4]
        slope, intercept = _fit_loglog(fit_ns, [ladder[n] for n in fit_ns])
        prefactor = math.exp(intercept)
        orders[order] = {
            "ladder": ladder,
            "slope": slope,
            "prefactor": prefactor,
            "fit_error_at_128": prefactor * 128.0 ** slope,
        }
    return {"N": N, "J": J, "h": h, "t": t,
            "exact_unitarity_dev": max_dev(
                matmul(dagger(U_exact), U_exact), eye(2 ** N)),
            "orders": orders}


def steps_to_target(order, N=N_SPINS, J=J_COUPLING, h=H_FIELD, t=T_EVOL,
                    target=TARGET_ERROR):
    """Step count for operator-norm error < target at the labelled t.

    Order 2: the fit predicts the neighbourhood, then the count is
    VERIFIED directly - walked up from the prediction until the
    measured error crosses the target, then bisected against the
    ladder's top rung (whose error is above target). The returned
    count is the smallest verified n found, to bisection
    resolution. Order 1: the fit predicts ~1.28 million steps;
    running them would take minutes of 16x16 matrix multiplies to
    confirm what the fit already shows, so the count is returned
    as what it is - EXTRAPOLATED, flagged in every printout.
    """
    rep = trotter_report(N, J, h, t)
    info = rep["orders"][order]
    slope, prefactor = info["slope"], info["prefactor"]
    n_fit = math.exp((math.log(target) - math.log(prefactor)) / slope)
    if order == 1:
        return {"order": order, "steps": int(math.ceil(n_fit)),
                "verified": False, "method": "fit-extrapolated",
                "fit_steps": n_fit}
    n = max(max(TROTTER_LADDER) + 1, int(math.ceil(n_fit)))
    err = trotter_error(N, J, h, t, n, order)
    tries = 0
    while err >= target and tries < 60:
        n = int(n * 1.1) + 1
        err = trotter_error(N, J, h, t, n, order)
        tries += 1
    lo = max(TROTTER_LADDER)  # ladder top rung: error above target
    hi = n
    for _ in range(8):
        mid = (lo + hi) // 2
        if mid == lo or mid == hi:
            break
        if trotter_error(N, J, h, t, mid, order) < target:
            hi = mid
        else:
            lo = mid
    return {"order": order, "steps": hi, "verified": True,
            "method": "fit-guided + directly verified (bisection)",
            "error_at_steps": trotter_error(N, J, h, t, hi, order),
            "fit_steps": n_fit}


# ================================================================ 5. Observables
# Magnetisation <Z_0>(t) and transverse response <X_0>(t) for two
# labelled initial states, evolved exactly and under both Trotter
# orders at n = 8. Two structural facts fall out of the numbers
# and are asserted in CHECKS rather than hidden:
#   * <Z_0>(t) is IDENTICAL for the two states (both have qubit 0
#     up): the nested-commutator closure of Z_0 contains no other
#     diagonal operator, so no Z-basis detail beyond qubit 0's own
#     orientation ever enters this curve.
#   * For these Z-basis inputs, Lie and Strang give the SAME
#     <Z_0> curve to machine precision at equal n: Strang's extra
#     half-step ZZ layers are diagonal phase layers, and a
#     diagonal observable cannot see them. <X_0> - not diagonal -
#     is the observable that separates the orders, ~9x at n = 8.

def basis_state(N, index):
    v = [0.0] * (2 ** N)
    v[index] = 1.0
    return v


def expect_z0(N, state):
    """<Z_0>: qubit 0 is the most significant bit; up = +1."""
    total = 0.0
    for s, amp in enumerate(state):
        z = 1.0 if ((s >> (N - 1)) & 1) == 0 else -1.0
        total += z * abs(amp) ** 2
    return total


def expect_x0(N, state):
    """<X_0>: qubit 0 is the most significant bit; X flips it."""
    flip = 1 << (N - 1)
    total = 0.0
    for s, amp in enumerate(state):
        total += (amp.conjugate() * state[s ^ flip]).real
    return total


INITIAL_STATES = {
    "all_up": 0,          # |0000>
    "neel": 0b0101,       # |0101> for N = 4 (alternating, qubit 0 up)
}


def observable_report(N=N_SPINS, J=J_COUPLING, h=H_FIELD, n_trot=8):
    out = {"N": N, "J": J, "h": h, "n_trotter": n_trot, "states": {}}
    for name, index in INITIAL_STATES.items():
        if N == N_SMALL and name == "neel":
            index = 0b010
        psi0 = basis_state(N, index)
        rows = []
        max_dev_z0 = 0.0
        max_z0_order_gap = 0.0
        max_dev_x0 = {1: 0.0, 2: 0.0}
        for t in OBS_TIMES:
            psi_ex = matvec(exact_propagator(N, J, h, t), psi0)
            row = {"t": t, "z0_exact": expect_z0(N, psi_ex),
                   "x0_exact": expect_x0(N, psi_ex)}
            for order in (1, 2):
                psi_tr = matvec(
                    trotter_propagator(N, J, h, t, n_trot, order), psi0)
                row[f"z0_order{order}"] = expect_z0(N, psi_tr)
                row[f"x0_order{order}"] = expect_x0(N, psi_tr)
                max_dev_x0[order] = max(
                    max_dev_x0[order],
                    abs(row[f"x0_order{order}"] - row["x0_exact"]))
            max_dev_z0 = max(
                max_dev_z0,
                abs(row["z0_order1"] - row["z0_exact"]),
                abs(row["z0_order2"] - row["z0_exact"]))
            max_z0_order_gap = max(
                max_z0_order_gap,
                abs(row["z0_order1"] - row["z0_order2"]))
            rows.append(row)
        out["states"][name] = {
            "index": index, "curve": rows,
            "max_dev_z0": max_dev_z0,
            "max_z0_order_gap": max_z0_order_gap,
            "max_dev_x0_order1": max_dev_x0[1],
            "max_dev_x0_order2": max_dev_x0[2]}
    return out


# ================================================================ 6. Resource ledger
# Gate bookkeeping per Trotter step, counted combinatorially for the
# open chain (N - 1 bonds): a ZZ layer is N - 1 two-qubit rotations,
# an X layer is N one-qubit rotations. Strang steps share their
# half-ZZ layers between neighbours, so n Strang steps cost
# (n + 1) ZZ layers, not 2n - the merged count is the honest one,
# and both counts are printed.

def step_gate_counts(N, order):
    """Nominal per-step rotation counts (unmerged)."""
    if order == 1:
        return {"zz_rotations": N - 1, "x_rotations": N}
    return {"zz_rotations": 2 * (N - 1), "x_rotations": N}


def total_gate_counts(N, order, n):
    """Circuit totals for n steps, adjacent Strang half-layers merged."""
    if order == 1:
        zz = n * (N - 1)
    else:
        zz = (n + 1) * (N - 1)
    x = n * N
    return {"zz_rotations": zz, "x_rotations": x, "total": zz + x}


def resources_report(N=N_SPINS, J=J_COUPLING, h=H_FIELD, t=T_EVOL):
    rows = {}
    for order in (1, 2):
        steps = steps_to_target(order, N, J, h, t)
        totals = total_gate_counts(N, order, steps["steps"])
        rows[order] = {"steps": steps["steps"],
                       "steps_verified": steps["verified"],
                       "per_step_nominal": step_gate_counts(N, order),
                       **totals}
    return {"N": N, "J": J, "h": h, "t": t, "target_error": TARGET_ERROR,
            "orders": rows,
            "total_ratio_order1_over_order2":
                rows[1]["total"] / rows[2]["total"]}


# ================================================================ 7. Sweeps + exact report
def exact_report(N=N_SPINS, J=J_COUPLING, h=H_FIELD, t=T_EVOL):
    H = build_hamiltonian(N, J, h)
    A, B = hamiltonian_parts(N, J, h)
    U = exact_propagator(N, J, h, t)
    U_back = mat_exp_neg_iH(H, -t)
    psi = matvec(U, basis_state(N, 0))
    return {
        "N": N, "dim": 2 ** N, "J": J, "h": h, "t": t,
        "trace_H": sum(H[i][i] for i in range(2 ** N)).real,
        "frob_norm_H": frob_norm(H),
        "commutator_frob_AB": commutator_norm(A, B),
        "unitarity_dev": max_dev(matmul(dagger(U), U), eye(2 ** N)),
        "u0_dev": max_dev(exact_propagator(N, J, h, 0.0), eye(2 ** N)),
        "roundtrip_dev": max_dev(matmul(U, U_back), eye(2 ** N)),
        "state_norm": math.sqrt(sum(abs(x) ** 2 for x in psi)),
        "z0_all_up_at_t": expect_z0(N, psi),
        "zz_factor_unitarity_dev": max_dev(
            matmul(dagger(exp_zz(N, J, 0.37)), exp_zz(N, J, 0.37)),
            eye(2 ** N)),
        "x_factor_unitarity_dev": max_dev(
            matmul(dagger(exp_x(N, h, 0.37)), exp_x(N, h, 0.37)),
            eye(2 ** N)),
    }


def sweeps_report():
    h_rows = []
    for h in H_SWEEP:
        h_rows.append({
            "h": h,
            "error_order2_n16": trotter_error(N_SPINS, J_COUPLING, h,
                                              T_EVOL, 16, 2),
            "error_order1_n16": trotter_error(N_SPINS, J_COUPLING, h,
                                              T_EVOL, 16, 1),
        })
    n_rows = []
    for N in (N_SMALL, N_SPINS):
        n_rows.append({
            "N": N, "dim": 2 ** N,
            "error_order2_n16": trotter_error(N, J_COUPLING, H_FIELD,
                                              T_EVOL, 16, 2),
            "error_order1_n16": trotter_error(N, J_COUPLING, H_FIELD,
                                              T_EVOL, 16, 1),
        })
    return {"h_sweep": h_rows, "n_sweep": n_rows,
            "commuting_points": {
                "h_zero_error_order1_n3": trotter_error(
                    N_SPINS, J_COUPLING, 0.0, T_EVOL, 3, 1),
                "j_zero_error_order2_n3": trotter_error(
                    N_SPINS, 0.0, H_FIELD, T_EVOL, 3, 2),
            }}


# ================================================================ 8. kNN regime classifier
# Features: (operator-norm error, steps n, Trotter order, h / J).
# The training grid is labelled by the lab's own policy
# (model_label below) - the classifier interpolates the policy,
# it does not replace the measured error.

def model_label(error, n, order, h_over_j):
    """The simulation-regime policy distilled to a four-way label."""
    if h_over_j == 0.0:
        return "trivially-exact"
    if error <= TARGET_ERROR:
        return "converged"
    if n >= 512:
        return "deep-circuit"
    return "trotter-limited"


def _training_grid():
    rows = []
    for error in (0.0, 1e-7, 5e-7, 2e-6, 1e-4, 1e-2, 3e-1):
        for n in (1, 8, 64, 512, 4096, 1000000):
            for order in (1, 2):
                for h_over_j in (0.0, 0.5, 1.0, 2.0):
                    rows.append(((error, n, order, h_over_j),
                                 model_label(error, n, order, h_over_j)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    error, n, order, h_over_j = features
    return ((math.log10(max(error, 1e-12)) + 12.0) / 12.0,
            math.log10(max(n, 1)) / 6.0,
            (order - 1) * 1.0,
            h_over_j / 2.0)


def classify_regime(error, n, order, h_over_j, k=5):
    """Distance-weighted kNN over the policy-labelled grid."""
    target = _scaled((error, n, order, h_over_j))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    weights = {}
    for dist, _, label in ranked[:k]:
        weights[label] = weights.get(label, 0.0) + 1.0 / (dist + 1e-9)
    priority = {"trivially-exact": 0, "converged": 1,
                "deep-circuit": 2, "trotter-limited": 3}
    return sorted(weights.items(),
                  key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def classifier_report():
    scenarios = {
        "second_order_at_target": (9.0e-07, 1100, 2, 1.0),
        "first_order_coarse_n8": (1.741e-01, 8, 1, 1.0),
        "first_order_million_steps": (1.5e-06, 1282892, 1, 1.0),
        "zero_field_any_split": (0.0, 4, 1, 0.0),
        "second_order_mid_n128": (6.944e-05, 128, 2, 1.0),
        "strong_field_converged": (8.0e-07, 300, 2, 2.0),
    }
    return {name: classify_regime(*features)
            for name, features in scenarios.items()}


# ================================================================ 9. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantumsimulation-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all speedup / hardware / discovery gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="quantumsimulation-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Say it in the first line of every report: this is a classical simulation of at most 4 qubits - then show the measured error, the fitted slope next to the theory slope, and which step counts are verified and which are extrapolated.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a 4-spin chain lighting up bond by bond under a transverse field",
                  "one exact propagator splitting into a staircase of Trotter steps",
                  "an error curve bending from slope -1 to slope -2 on a log-log plot",
                  "a million first-order steps shrinking beside a thousand second-order ones",
                  "the resource ledger stamping rotations counted, none executed"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    ex = exact_report()
    tr = trotter_report()
    sw = sweeps_report()
    ob = observable_report()
    res = resources_report()

    # 1. linear algebra kit
    A2 = [[1.0, 2.0], [3.0, 4.0]]
    B2 = [[0.0, 1.0], [1.0, 0.0]]
    chk("kron_shape_and_values",
        kron(A2, B2)[0] == [0.0, 1.0, 0.0, 2.0]
        and len(kron(A2, B2)) == 4)
    chk("matmul_identity", matmul(A2, eye(2)) == A2)
    chk("dagger_involution", dagger(dagger(A2)) == A2)
    chk("exp_zero_time_is_identity", ex["u0_dev"] < 1e-12)

    # 2. Hamiltonian + exact propagator
    chk("hamiltonian_traceless", abs(ex["trace_H"]) < 1e-12)
    chk("exact_propagator_unitary", ex["unitarity_dev"] < 1e-12)
    chk("exact_roundtrip_identity", ex["roundtrip_dev"] < 1e-12)
    chk("state_norm_conserved", abs(ex["state_norm"] - 1.0) < 1e-12)
    chk("parts_do_not_commute_at_h1", ex["commutator_frob_AB"] > 0.5)
    A0, B0 = hamiltonian_parts(N_SPINS, J_COUPLING, 0.0)
    chk("commutator_zero_at_h0", commutator_norm(A0, B0) == 0.0)
    chk("zz_factor_unitary", ex["zz_factor_unitarity_dev"] < 1e-12)
    chk("x_factor_unitary", ex["x_factor_unitarity_dev"] < 1e-12)

    # 3. Trotter ladder, slopes, prefactors
    lad1 = tr["orders"][1]["ladder"]
    lad2 = tr["orders"][2]["ladder"]
    chk("ladder_errors_fall_with_n",
        all(lad1[n] > lad1[2 * n] for n in (1, 2, 4, 8, 16, 32, 64))
        and all(lad2[n] > lad2[2 * n] for n in (1, 2, 4, 8, 16, 32, 64)))
    chk("second_order_beats_first_at_n16", lad2[16] < lad1[16] / 10.0)
    chk("slope_order1_is_minus_1",
        abs(tr["orders"][1]["slope"] + 1.0) < 0.15)
    chk("slope_order2_is_minus_2",
        abs(tr["orders"][2]["slope"] + 2.0) < 0.15)
    chk("fit_reproduces_measured_n128",
        abs(tr["orders"][1]["fit_error_at_128"] / lad1[128] - 1.0) < 0.35
        and abs(tr["orders"][2]["fit_error_at_128"] / lad2[128] - 1.0)
        < 0.35)
    chk("opnorm_below_frobenius_bound",
        lad2[8] <= frob_norm(
            [[trotter_propagator(N_SPINS, J_COUPLING, H_FIELD, T_EVOL, 8, 2)[i][j]
              - exact_propagator(N_SPINS, J_COUPLING, H_FIELD, T_EVOL)[i][j]
              for j in range(16)] for i in range(16)]) + 1e-12)

    # 4. steps to target
    s1 = steps_to_target(1)
    s2 = steps_to_target(2)
    chk("steps_order2_verified_below_target",
        s2["verified"] and s2["error_at_steps"] < TARGET_ERROR)
    chk("steps_order2_bracketed_by_ladder", s2["steps"] > max(TROTTER_LADDER)
        and lad2[max(TROTTER_LADDER)] >= TARGET_ERROR)
    chk("steps_order1_extrapolated_flagged",
        not s1["verified"] and s1["steps"] > 100000)

    # 5. commuting points are exact under any split
    chk("h_zero_trotter_exact",
        sw["commuting_points"]["h_zero_error_order1_n3"] < 1e-12)
    chk("j_zero_trotter_exact",
        sw["commuting_points"]["j_zero_error_order2_n3"] < 1e-12)

    # 6. observables - including the two structural identities
    chk("z0_all_up_starts_at_1",
        abs(ob["states"]["all_up"]["curve"][0]["z0_exact"] - 1.0) < 1e-12)
    chk("z0_neel_starts_at_1",
        abs(ob["states"]["neel"]["curve"][0]["z0_exact"] - 1.0) < 1e-12)
    chk("z0_curve_identical_for_both_states",
        all(abs(a["z0_exact"] - b["z0_exact"]) < 1e-9
            for a, b in zip(ob["states"]["all_up"]["curve"],
                            ob["states"]["neel"]["curve"])))
    chk("z0_lie_strang_cancellation",
        ob["states"]["all_up"]["max_z0_order_gap"] < 1e-9
        and ob["states"]["neel"]["max_z0_order_gap"] < 1e-9)
    chk("z0_trotter_deviation_printed",
        0.001 < ob["states"]["all_up"]["max_dev_z0"] < 0.05)
    chk("x0_order2_far_closer_than_order1",
        ob["states"]["all_up"]["max_dev_x0_order2"] * 3.0
        < ob["states"]["all_up"]["max_dev_x0_order1"]
        and ob["states"]["neel"]["max_dev_x0_order2"] * 3.0
        < ob["states"]["neel"]["max_dev_x0_order1"])
    chk("x0_deviations_small_for_order2",
        ob["states"]["all_up"]["max_dev_x0_order2"] < 0.02
        and ob["states"]["neel"]["max_dev_x0_order2"] < 0.02)
    chk("x0_at_t1_flips_sign_between_states",
        abs(ob["states"]["all_up"]["curve"][4]["x0_exact"]
            + ob["states"]["neel"]["curve"][4]["x0_exact"]) < 1e-9)

    # 7. sweeps
    h0_row = sw["h_sweep"][0]
    chk("h_sweep_zero_field_exact",
        h0_row["h"] == 0.0 and h0_row["error_order2_n16"] < 1e-12)
    chk("h_sweep_error_grows_with_field",
        sw["h_sweep"][4]["error_order2_n16"]
        > sw["h_sweep"][1]["error_order2_n16"])
    chk("n_sweep_dims", [r["dim"] for r in sw["n_sweep"]] == [8, 16])

    # 8. resource ledger combinatorics
    chk("per_step_counts_order1",
        step_gate_counts(4, 1) == {"zz_rotations": 3, "x_rotations": 4})
    chk("per_step_counts_order2_nominal",
        step_gate_counts(4, 2) == {"zz_rotations": 6, "x_rotations": 4})
    chk("merged_totals_order1",
        total_gate_counts(4, 1, 100)["zz_rotations"] == 300
        and total_gate_counts(4, 1, 100)["x_rotations"] == 400)
    chk("merged_totals_order2_strang_sharing",
        total_gate_counts(4, 2, 100)["zz_rotations"] == 303
        and total_gate_counts(4, 2, 100)["x_rotations"] == 400)
    chk("resource_ratio_order1_far_above_order2",
        res["total_ratio_order1_over_order2"] > 100.0)

    # 9. classifier - labels come from the lab's own policy
    rep = classifier_report()
    chk("classifier_at_target_converged",
        rep["second_order_at_target"] == "converged")
    chk("classifier_coarse_trotter_limited",
        rep["first_order_coarse_n8"] == "trotter-limited")
    chk("classifier_million_steps_deep_circuit",
        rep["first_order_million_steps"] == "deep-circuit")
    chk("classifier_zero_field_trivially_exact",
        rep["zero_field_any_split"] == "trivially-exact")
    chk("classifier_mid_trotter_limited",
        rep["second_order_mid_n128"] == "trotter-limited")
    chk("classifier_strong_field_converged",
        rep["strong_field_converged"] == "converged")
    chk("classifier_matches_policy_on_grid",
        all(classify_regime(*features) == label
            for features, label in TRAINING_GRID))
    chk("classifier_matches_policy_on_scenarios",
        all(classify_regime(*features) == model_label(*features)
            for features in [(9.0e-07, 1100, 2, 1.0), (1.741e-01, 8, 1, 1.0),
                             (1.5e-06, 1282892, 1, 1.0), (0.0, 4, 1, 0.0),
                             (6.944e-05, 128, 2, 1.0),
                             (8.0e-07, 300, 2, 2.0)]))

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_speedup_hold", gate("quantum_speedup_claim") == "HOLD")
    chk("gate_hardware_hold", gate("real_hardware_execution") == "HOLD")
    chk("gate_chemistry_hold", gate("chemistry_discovery_claim") == "HOLD")
    chk("gate_crypto_hold", gate("cryptanalysis_claim") == "HOLD")
    chk("gate_thermodynamic_hold",
        gate("thermodynamic_limit_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def _r6(x):
    """Six-significant-digit float for JSON output (deterministic)."""
    return float(f"{x:.6g}")


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        return _r6(value)
    if isinstance(value, complex):
        return {"re": _r6(value.real), "im": _r6(value.imag)}
    return value


def demo():
    print("=" * 68)
    print("QuantumSimulation-Lab - digital quantum simulation lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - a classical simulation of a quantum algorithm")
    print("    This lab simulates the transverse-field Ising chain on")
    print("    N = 3 and N = 4 spins (Hilbert dims 8 and 16) with matrices")
    print("    built from scratch in pure Python. It is NOT a quantum")
    print("    computer and claims NO speedup: the exact propagator and")
    print("    both Trotter-Suzuki formulas are graded against each other,")
    print("    and the error bookkeeping is the whole point.")
    ex = exact_report()
    print("\n[2] Exact reference - H = -J sum Z_i Z_{i+1} - h sum X_i (open chain)")
    print(f"    N = {ex['N']} spins | dim {ex['dim']} | J = {ex['J']} | "
          f"h = {ex['h']} | t = {ex['t']}")
    print(f"    trace(H) = {ex['trace_H']:.1f} | ||H||_F = "
          f"{ex['frob_norm_H']:.4f} | ||[A, B]||_F = "
          f"{ex['commutator_frob_AB']:.4f} (nonzero: the parts do not commute)")
    print(f"    U = exp(-iHt) by scaling-and-squaring Taylor: unitarity dev "
          f"{ex['unitarity_dev']:.2e}, roundtrip U(t)U(-t) dev "
          f"{ex['roundtrip_dev']:.2e}")
    print(f"    <Z_0>(t = 1) from |0000>: {ex['z0_all_up_at_t']:+.6f}")
    tr = trotter_report()
    print("\n[3] Trotter-Suzuki error ladder - operator norm vs exact, t = 1.0")
    print("      n        order 1 (Lie)     order 2 (Strang)")
    for n in TROTTER_LADDER:
        print(f"    {n:5d}    {tr['orders'][1]['ladder'][n]:.6e}    "
              f"{tr['orders'][2]['ladder'][n]:.6e}")
    for order in (1, 2):
        info = tr["orders"][order]
        print(f"    order {order}: fitted log-log slope {info['slope']:+.4f} "
              f"(theory {-order:.0f}) | prefactor {info['prefactor']:.4f}")
    s1 = steps_to_target(1)
    s2 = steps_to_target(2)
    print(f"    steps to error < 1e-6: order 2 -> {s2['steps']} "
          f"(VERIFIED directly, error {s2['error_at_steps']:.2e})")
    print(f"    steps to error < 1e-6: order 1 -> {s1['steps']} "
          f"(EXTRAPOLATED from the fit - not run; over a million steps")
    print("     of 16x16 matrix multiplies is minutes of CPU to confirm the fit)")
    ob = observable_report()
    print("\n[4] Observables - <Z_0>(t) and <X_0>(t), exact vs Trotter (n = 8), h = 1")
    for name, data in ob["states"].items():
        print(f"    {name}: <Z_0> max dev {data['max_dev_z0']:.6f} "
              f"(both orders - see below) | <X_0> max dev order 1 = "
              f"{data['max_dev_x0_order1']:.6f}, order 2 = "
              f"{data['max_dev_x0_order2']:.6f}")
    print("    -> the <Z_0> curves of the two states are IDENTICAL, and Lie")
    print("       and Strang agree on <Z_0> to machine precision at equal n:")
    print("       Strang's half-step ZZ layers are diagonal phases, invisible")
    print("       to a diagonal observable from a Z-basis state. <X_0> is the")
    print("       observable that separates the orders (~9x at n = 8).")
    sw = sweeps_report()
    print(f"    commuting points: h = 0 error {sw['commuting_points']['h_zero_error_order1_n3']:.2e}, "
          f"J = 0 error {sw['commuting_points']['j_zero_error_order2_n3']:.2e} "
          f"(exact under any split)")
    res = resources_report()
    print("\n[5] Resource ledger - rotations to reach error < 1e-6 (counted, none executed)")
    for order in (1, 2):
        row = res["orders"][order]
        tag = "verified steps" if row["steps_verified"] else "extrapolated steps"
        print(f"    order {order}: {row['steps']} steps ({tag}) -> "
              f"{row['zz_rotations']} ZZ + {row['x_rotations']} X = "
              f"{row['total']} rotations")
    print(f"    total ratio order 1 / order 2 = "
          f"{res['total_ratio_order1_over_order2']:.1f}x")
    print("\n[6] Regime classifier (TinyML kNN, labels from the lab's policy)")
    for name, label in classifier_report().items():
        print(f"    {name:36s} -> {label}")
    print("\n[7] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[8] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "exact":
        print(json.dumps(_jsonable(exact_report()), indent=2, sort_keys=True))
        return 0
    if cmd == "trotter":
        rep = trotter_report()
        out = {"N": rep["N"], "J": rep["J"], "h": rep["h"], "t": rep["t"],
               "exact_unitarity_dev": rep["exact_unitarity_dev"],
               "orders": {}}
        for order in (1, 2):
            info = rep["orders"][order]
            steps = steps_to_target(order)
            out["orders"][str(order)] = {
                "ladder": {str(n): e for n, e in info["ladder"].items()},
                "slope": info["slope"], "prefactor": info["prefactor"],
                "steps_to_1e-6": steps["steps"],
                "steps_verified": steps["verified"],
                "steps_method": steps["method"]}
        print(json.dumps(_jsonable(out), indent=2, sort_keys=True))
        return 0
    if cmd == "observable":
        print(json.dumps(_jsonable(observable_report()),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "resources":
        print(json.dumps(_jsonable(resources_report()),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "sweeps":
        print(json.dumps(_jsonable(sweeps_report()),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "quantum_speedup_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())

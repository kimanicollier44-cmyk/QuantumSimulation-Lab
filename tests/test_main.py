"""Tests for QuantumSimulation-Lab: the linear-algebra kit, the exact
propagator receipts, the Trotter ladder and fitted slopes, the
verified / extrapolated step counts, the commuting points, the
observable identities, the resource combinatorics, the kNN policy,
HOLD gates, and determinism."""
import math

import main


EX = main.exact_report()
TR = main.trotter_report()
OB = main.observable_report()
SW = main.sweeps_report()


# ---------------------------------------------------------------- lin-alg kit
def test_kron_and_matmul():
    A = [[1.0, 2.0], [3.0, 4.0]]
    B = [[0.0, 1.0], [1.0, 0.0]]
    K = main.kron(A, B)
    assert len(K) == 4 and K[0] == [0.0, 1.0, 0.0, 2.0]
    assert main.matmul(A, main.eye(2)) == A
    assert main.dagger(main.dagger(A)) == A


def test_exp_of_zero_time_is_identity():
    assert EX["u0_dev"] < 1e-12


# ---------------------------------------------------------------- exact reference
def test_hamiltonian_is_traceless():
    assert abs(EX["trace_H"]) < 1e-12


def test_exact_propagator_is_unitary():
    assert EX["unitarity_dev"] < 1e-12
    assert EX["roundtrip_dev"] < 1e-12


def test_state_norm_is_conserved():
    assert abs(EX["state_norm"] - 1.0) < 1e-12


def test_parts_do_not_commute_at_labelled_field():
    assert EX["commutator_frob_AB"] > 0.5
    A0, B0 = main.hamiltonian_parts(4, 1.0, 0.0)
    assert main.commutator_norm(A0, B0) == 0.0


def test_trotter_factors_are_unitary():
    assert EX["zz_factor_unitarity_dev"] < 1e-12
    assert EX["x_factor_unitarity_dev"] < 1e-12


# ---------------------------------------------------------------- Trotter ladder
def test_ladder_errors_fall_with_n():
    for order in (1, 2):
        lad = TR["orders"][order]["ladder"]
        assert all(lad[n] > lad[2 * n] for n in (1, 2, 4, 8, 16, 32, 64))


def test_second_order_beats_first_at_n16():
    assert TR["orders"][2]["ladder"][16] < TR["orders"][1]["ladder"][16] / 10.0


def test_fitted_slopes_match_theory():
    assert abs(TR["orders"][1]["slope"] + 1.0) < 0.15
    assert abs(TR["orders"][2]["slope"] + 2.0) < 0.15


def test_fit_reproduces_measured_ladder_top():
    for order in (1, 2):
        fit = TR["orders"][order]["fit_error_at_128"]
        measured = TR["orders"][order]["ladder"][128]
        assert abs(fit / measured - 1.0) < 0.35


# ---------------------------------------------------------------- steps to target
def test_steps_order2_verified_directly():
    s2 = main.steps_to_target(2)
    assert s2["verified"] is True
    assert s2["error_at_steps"] < main.TARGET_ERROR
    assert s2["steps"] > max(main.TROTTER_LADDER)


def test_steps_order1_extrapolated_and_flagged():
    s1 = main.steps_to_target(1)
    assert s1["verified"] is False
    assert s1["steps"] > 100000


# ---------------------------------------------------------------- commuting points
def test_zero_field_is_exact_under_any_split():
    assert SW["commuting_points"]["h_zero_error_order1_n3"] < 1e-12


def test_zero_coupling_is_exact_under_any_split():
    assert SW["commuting_points"]["j_zero_error_order2_n3"] < 1e-12


# ---------------------------------------------------------------- observables
def test_z0_starts_at_one_for_both_states():
    for name in ("all_up", "neel"):
        assert abs(OB["states"][name]["curve"][0]["z0_exact"] - 1.0) < 1e-12


def test_z0_curve_identical_for_both_states():
    for a, b in zip(OB["states"]["all_up"]["curve"],
                    OB["states"]["neel"]["curve"]):
        assert abs(a["z0_exact"] - b["z0_exact"]) < 1e-9


def test_z0_lie_strang_cancellation():
    for name in ("all_up", "neel"):
        assert OB["states"][name]["max_z0_order_gap"] < 1e-9
        assert 0.001 < OB["states"][name]["max_dev_z0"] < 0.05


def test_x0_separates_the_orders():
    for name in ("all_up", "neel"):
        data = OB["states"][name]
        assert data["max_dev_x0_order2"] * 3.0 < data["max_dev_x0_order1"]
        assert data["max_dev_x0_order2"] < 0.02


def test_x0_at_t1_flips_sign_between_states():
    assert abs(OB["states"]["all_up"]["curve"][4]["x0_exact"]
               + OB["states"]["neel"]["curve"][4]["x0_exact"]) < 1e-9


# ---------------------------------------------------------------- sweeps
def test_h_sweep_zero_field_exact_and_growth():
    rows = SW["h_sweep"]
    assert rows[0]["h"] == 0.0 and rows[0]["error_order2_n16"] < 1e-12
    assert rows[4]["error_order2_n16"] > rows[1]["error_order2_n16"]


def test_n_sweep_dimensions():
    assert [r["dim"] for r in SW["n_sweep"]] == [8, 16]


# ---------------------------------------------------------------- resources
def test_per_step_gate_counts():
    assert main.step_gate_counts(4, 1) == {"zz_rotations": 3, "x_rotations": 4}
    assert main.step_gate_counts(4, 2) == {"zz_rotations": 6, "x_rotations": 4}


def test_merged_gate_totals():
    assert main.total_gate_counts(4, 1, 100)["total"] == 700
    merged = main.total_gate_counts(4, 2, 100)
    assert merged["zz_rotations"] == 303  # (n + 1) layers, Strang sharing
    assert merged["x_rotations"] == 400


def test_resource_ratio_is_over_100x():
    assert main.resources_report()["total_ratio_order1_over_order2"] > 100.0


# ---------------------------------------------------------------- classifier
def test_classifier_verdicts():
    rep = main.classifier_report()
    assert rep["second_order_at_target"] == "converged"
    assert rep["first_order_coarse_n8"] == "trotter-limited"
    assert rep["first_order_million_steps"] == "deep-circuit"
    assert rep["zero_field_any_split"] == "trivially-exact"
    assert rep["second_order_mid_n128"] == "trotter-limited"
    assert rep["strong_field_converged"] == "converged"


def test_classifier_matches_policy_on_grid():
    for features, label in main.TRAINING_GRID:
        assert main.classify_regime(*features) == label


# ---------------------------------------------------------------- gates + seats
def test_hold_gates():
    assert len(main.HOLD_GATES) == 14
    assert main.gate("quantum_speedup_claim") == "HOLD"
    assert main.gate("real_hardware_execution") == "HOLD"
    assert main.gate("chemistry_discovery_claim") == "HOLD"
    assert main.gate("cryptanalysis_claim") == "HOLD"
    assert main.gate("run_simulation") == "PROCEED"


def test_hold_demo_exits_2():
    assert main.main(["hold-demo"]) == 2
    assert main.main(["hold-demo", "quantum_speedup_claim"]) == 2
    assert main.main(["hold-demo", "run_simulation"]) == 0


def test_council_seats_never_override():
    brains = main.brains_report()
    assert brains["decider"]["seat"] == "Gemini Argon 4 Extended Thinking"
    assert brains["decider"]["can_override_hold"] is False
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


# ---------------------------------------------------------------- determinism
def test_checks_all_pass():
    checks = main.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]


def test_demo_is_deterministic(capsys):
    main.demo()
    first = capsys.readouterr().out
    main.demo()
    second = capsys.readouterr().out
    assert first == second

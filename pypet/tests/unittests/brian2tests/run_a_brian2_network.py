try:
    import brian2
    from brian2 import (
        NeuronGroup,
        PopulationRateMonitor,
        SpikeMonitor,
        StateMonitor,
        defaultclock,
        linspace,
        ms,
        msecond,
        mV,
        nA,
        nS,
        pF,
        run,
    )
except ImportError:
    brian2 = None


def run_network():

    monitor_dict = {}
    defaultclock.dt = 0.01 * ms

    C = 281 * pF  # noqa: F841
    gL = 30 * nS  # noqa: F841
    EL = -70.6 * mV
    VT = -50.4 * mV  # noqa: F841
    DeltaT = 2 * mV  # noqa: F841
    tauw = 40 * ms  # noqa: F841
    a = 4 * nS
    b = 0.08 * nA  # noqa: F841
    I = 8 * nA  # noqa: F841
    Vcut = "vm>2*mV"  # practical threshold condition
    N = 10

    reset = "vm=Vr;w+=b"

    eqs = """
    dvm/dt=(gL*(EL-vm)+gL*DeltaT*exp((vm-VT)/DeltaT)+I-w)/C : volt
    dw/dt=(a*(vm-EL)-w)/tauw : amp
    Vr:volt
    """

    neuron = NeuronGroup(N, model=eqs, threshold=Vcut, reset=reset)
    neuron.vm = EL
    neuron.w = a * (neuron.vm - EL)
    neuron.Vr = linspace(-48.3 * mV, -47.7 * mV, N)  # bifurcation parameter

    # run(25*msecond,report='text') # we discard the first spikes

    MSpike = SpikeMonitor(neuron, variables=["vm"])  # record Vr and w at spike times
    MPopRate = PopulationRateMonitor(neuron)

    MMultiState = StateMonitor(neuron, ["w", "vm"], record=[6, 7, 8, 9])

    run(10 * msecond, report="text")

    monitor_dict["SpikeMonitor"] = MSpike
    monitor_dict["MultiState"] = MMultiState
    monitor_dict["PopulationRateMonitor"] = MPopRate

    return monitor_dict


if __name__ == "__main__":
    if brian2 is not None:
        run_network()

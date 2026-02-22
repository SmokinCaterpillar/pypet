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

    281 * pF
    30 * nS
    EL = -70.6 * mV
    -50.4 * mV
    2 * mV
    40 * ms
    a = 4 * nS
    0.08 * nA
    8 * nA
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

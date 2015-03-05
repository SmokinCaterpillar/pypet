
.. _example-06:

====================
Parameter Presetting
====================

Download: :download:`example_06_parameter_presetting.py <../../../examples/example_06_parameter_presetting.py>`

We will reuse some stuff from the previous example :ref:`example-05`:

* Our main euler simulation job `euler_scheme`

* The `FunctionParameter` to store source code

We will execute the same euler simulation as before, but now with a different
differential equation yielding the `Roessler Attractor`_.
If you erase the statement

    `traj.f_preset_parameter('diff_name', 'diff_roessler')`

you will end up with the same results as in the previous example.

.. _Roessler Attractor: https://en.wikipedia.org/wiki/R%C3%B6ssler_attractor

.. literalinclude:: ../../../examples/example_06_parameter_presetting.py
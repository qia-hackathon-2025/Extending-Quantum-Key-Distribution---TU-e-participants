# Tutorial Overview

Welcome to the SquidASM tutorial. In this tutorial you will be introduced to the objects and concepts necessary to develop applications and evaluate applications using the SquidASM simulation.

## Getting Started

Before starting the tutorial, it is recommended to first install SquidASM and the required components. This process is described in the [Installation Guide](../installation.md).

The tutorial sections are accompanied by code examples in the SquidASM package located in the `examples/tutorial` folder of SquidASM. The code examples shown in this tutorial are part of these examples. It is useful to browse through the examples when reading the tutorial to obtain the full context of the snippets.

## Tutorial Structure

### Files

A simulation of a quantum network application has roughly three components: the network, the application and the simulation. In order to encourage modularity we split the code into three separate files, in line with the conceptual components:

**`application.py`**
: This file contains the individual programs that run on end nodes. So it will typically contain the `AliceProgram` and `BobProgram` or the `ServerProgram` and `ClientProgram`.

**`config.yaml`**
: The file that specifies the network. It controls the network layout and end node labels. Moreover, it specifies the link and node types and properties.

**`run_simulation.py`**
: The executable file that will run the simulation. In its most simple form it loads the programs from `application.py` and the network from `config.yaml` and then runs the simulation. In more advanced form it may specify various simulation settings, automate multiple simulation runs and handle the simulation output.

### Learning Path

The tutorial sections are designed to be followed in order:

1. **[Section 1: Basics](./1_basics.md)** - Introduction to classical and quantum communication, EPR pairs, and local qubits
2. **[Section 2: NetQASM](./2_netqasm.md)** - Understanding NetQASM language, instruction queues, and Future objects
3. **[Section 3: Simulation Control](./3_simulation_control.md)** - Running simulations, getting output, and logging
4. **[Section 4: Network Configuration](./4_network_configuration.md)** - Configuring networks, stack types, link types, and parameter sweeping
5. **[Section 5: Multi-Node Networks](./5_multi_node.md)** - Extending applications to networks with more than two nodes
6. **[Section 6: Parameter Sweeping](./6_parameter_sweeping.md)** - Automating parameter variations and analyzing results

Each section builds upon the previous ones. The first and second sections focus exclusively on `application.py`, the third section explains `run_simulation.py`, and the fourth section explains the network specification using `config.yaml`.

## About NetQASM

The applications for SquidASM need to be written almost entirely using the [NetQASM SDK](https://github.com/QuTech-Delft/netqasm) package.

NetQASM has its own [documentation](https://netqasm.readthedocs.io/), with a [tutorial](https://netqasm.readthedocs.io/en/latest/quickstart.html) and [API documentation](https://netqasm.readthedocs.io/en/latest/netqasm.sdk.html).

**Important Note:** We do not recommend starting with the NetQASM tutorial initially, as there are differences in syntax between what the NetQASM tutorial introduces and what SquidASM requires from its applications. This tutorial will introduce NetQASM as well in a way that is compatible with SquidASM.

Once you have completed this tutorial, we do recommend using the NetQASM API documentation for more advanced features.

## Running Examples

To run any of the tutorial examples, first navigate to the example directory:

```bash
cd examples/tutorial/1_Basics
```

Then run the simulation:

```bash
python3 run_simulation.py
```

All examples are fully functional and can be executed immediately.

## Quick Reference

For quick lookups of common concepts, refer to the [Appendix: Terminology](./appendix_terminology.md).

## What You'll Learn

By the end of this tutorial, you will understand:

- How to structure a quantum network application
- How to use classical sockets for message passing
- How to generate and use EPR pairs for entanglement
- How to work with the NetQASM connection and instruction queues
- How to interpret and debug simulation output
- How to configure networks with different quantum device models and link types
- How to extend applications to multi-node scenarios
- How to perform parameter sweeping for performance analysis

from application import AliceProgram, BobProgram

from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# import network configuration from file
cfg = StackNetworkConfig.from_file("config.yaml")

# Initialize protocol programs
alice_program = AliceProgram()
bob_program = BobProgram()

# Map each network node to its corresponding protocol program
programs = {"Alice": alice_program,
            "Bob": bob_program}

# Run the simulation
run(
    config=cfg,
    programs=programs,
    num_times=1,
)

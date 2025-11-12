import netsquid as ns

from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class AliceProgram(Program):
    NODE_NAME = "Alice"
    PEER_BOB = "Bob"
    PEER_CHARLIE = "Charlie"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name=f"program_{self.NODE_NAME}",
            csockets=[self.PEER_BOB, self.PEER_CHARLIE],
            epr_sockets=[self.PEER_BOB, self.PEER_CHARLIE],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        # get classical sockets
        csocket_bob = context.csockets[self.PEER_BOB]
        csocket_charlie = context.csockets[self.PEER_CHARLIE]
        # get EPR sockets
        epr_socket_bob = context.epr_sockets[self.PEER_BOB]
        epr_socket_charlie = context.epr_sockets[self.PEER_CHARLIE]
        # get connection to QNPU
        connection = context.connection

        print(f"{ns.sim_time()} ns: Hello from {self.NODE_NAME}")
        return {}


class BobProgram(Program):
    NODE_NAME = "Bob"
    PEER_ALICE = "Alice"
    PEER_CHARLIE = "Charlie"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name=f"program_{self.NODE_NAME}",
            csockets=[self.PEER_ALICE, self.PEER_CHARLIE],
            epr_sockets=[self.PEER_ALICE, self.PEER_CHARLIE],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        # get classical sockets
        csocket_alice = context.csockets[self.PEER_ALICE]
        csocket_charlie = context.csockets[self.PEER_CHARLIE]
        # get EPR sockets
        epr_socket_alice = context.epr_sockets[self.PEER_ALICE]
        epr_socket_charlie = context.epr_sockets[self.PEER_CHARLIE]
        # get connection to QNPU
        connection = context.connection

        print(f"{ns.sim_time()} ns: Hello from {self.NODE_NAME}")
        return {}


class CharlieProgram(Program):
    NODE_NAME = "Charlie"
    PEER_ALICE = "Alice"
    PEER_BOB = "Bob"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name=f"program_{self.NODE_NAME}",
            csockets=[self.PEER_ALICE, self.PEER_BOB],
            epr_sockets=[self.PEER_ALICE, self.PEER_BOB],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        # get classical sockets
        csocket_alice = context.csockets[self.PEER_ALICE]
        csocket_bob = context.csockets[self.PEER_BOB]
        # get EPR sockets
        epr_socket_alice = context.epr_sockets[self.PEER_ALICE]
        epr_socket_bob = context.epr_sockets[self.PEER_BOB]
        # get connection to QNPU
        connection = context.connection

        print(f"{ns.sim_time()} ns: Hello from {self.NODE_NAME}")
        return {}


import unittest
import asyncio
import random
from main import Client, Server, TokenManager  # Adjust import according to your project structure
from main import NUMBER_OF_SERVERS, NUMBER_OF_CLIENTS, TOTAL_TOKENS, FAULTY_SERVERS, INITIAL_TOKENS_PER_CLIENT
from main import GET_TOKENS_COMMAND, PAY_COMMAND
import hashlib
import json


class ServerSimulation:
    def __init__(self):
        self.server_tasks = []
        self.servers = []

    async def initialize_servers(self, simulate_faults=False, delay=0):
        faulty_servers_indices = random.sample(range(NUMBER_OF_SERVERS), k=random.randint(0, FAULTY_SERVERS)) if (
            simulate_faults) else []
        print(f"Faulty: {len(faulty_servers_indices)}")
        self.servers = [Server(TokenManager(), i in faulty_servers_indices, delay) for i in range(NUMBER_OF_SERVERS)]
        self.server_tasks = [asyncio.create_task(server.start_server()) for server in self.servers]
        await asyncio.sleep(1)  # Wait for servers to initialize

    async def cancel_servers(self):
        for task in self.server_tasks:
            task.cancel()
        await asyncio.gather(*self.server_tasks, return_exceptions=True)


class TestUtility:
    FAIL = "Safety test failed: System states do not match"
    PASS = "Safety test passed: System maintained state consistency despite faults"

    @staticmethod
    def hash_state(state):
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_operations(num=10):
        return [(random.randint(1, NUMBER_OF_CLIENTS), random.randint(1, NUMBER_OF_CLIENTS)) for _ in range(num)]

    @staticmethod
    async def gather_states(client):
        states = {}
        for client_id in range(1, NUMBER_OF_CLIENTS + 1):
            states[client_id] = await client.gettokens(owner=client_id)
        return states

    @staticmethod
    def compare_states(state1, state2):
        return TestUtility.hash_state(state1) == TestUtility.hash_state(state2)


class Timeline:
    def __init__(self):
        self.timeline = []

    async def pay(self, client: Client, token_id: int, version: int, new_owner: int):
        print(f"START pay(id={token_id},version={version},new_owner={new_owner})")
        # Perform the pay operation
        payment_ack = await client.pay(token_id=token_id, version=version, new_owner=new_owner)
        event = {
            'command': PAY_COMMAND,
            'id': token_id,
            'version': version,
            'new_owner': new_owner
        }
        self.timeline.append((event, payment_ack))
        # Print the result of the pay operation
        print(f"RESPONSE {PAY_COMMAND}(id={token_id},version={version},new_owner={new_owner}) -> {payment_ack}")
        return payment_ack

    async def get_tokens(self, client: Client, owner: int):
        print(f"START {GET_TOKENS_COMMAND}({owner})")
        tokens = await client.gettokens(owner=owner)
        event = {
            'command': GET_TOKENS_COMMAND,
            'owner': owner
        }
        self.timeline.append((event, tokens))
        print(f"RESPONSE {GET_TOKENS_COMMAND}({owner}) -> {tokens}")
        return tokens


def generate_operations(it: int):
    """Generate a list of operations for testing."""
    return [(random.randint(1, NUMBER_OF_CLIENTS), random.randint(1, NUMBER_OF_CLIENTS)) for _ in range(it)]


async def perform_operations(client: Client, operations: list, timeline: Timeline):
    """Perform client operations and record them in a timeline."""
    client_tasks = []
    for old_owner, new_owner in operations:
        tokens = await timeline.get_tokens(client, old_owner)
        if tokens:
            token_id, version = random.choice(tokens)
            client_tasks.append(asyncio.create_task(timeline.pay(client, token_id, version + 1, new_owner)))
            client_tasks.append(asyncio.create_task(timeline.get_tokens(client, new_owner)))
    # Wait for all operations to complete
    await asyncio.gather(*client_tasks)


class LivenessTest(unittest.TestCase):
    def setUp(self):
        """Initialize resources before each test."""
        self.server_sim = ServerSimulation()
        self.client = Client()

    def tearDown(self):
        """Clean up resources after tests are finished."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.server_sim.cancel_servers())

    def run_async_test(self, coro):
        """Utility method to run coroutine tests."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    async def test_system_responsiveness(self):
        """Test to ensure that the system responds to 'gettokens' requests under fault conditions."""
        await self.server_sim.initialize_servers(simulate_faults=True, delay=1)
        # Simulate multiple concurrent 'gettokens' requests
        operations = [self.client.gettokens(owner=i) for i in range(1, NUMBER_OF_CLIENTS + 1)]
        responses = await asyncio.gather(*operations)

        # Check that all responses are received and are valid (not None or empty)
        for i, response in enumerate(responses, start=1):
            with self.subTest(i=i):
                self.assertIsNotNone(response, f"Failed to receive response for owner {i}")
                self.assertTrue(len(response) > 0, f"Received empty response for owner {i}")

        print("All 'gettokens' requests received valid responses.")


class TestPaymentOperations(unittest.TestCase):

    def setUp(self):
        self.server_sim = ServerSimulation()
        self.client = Client()

    def tearDown(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.server_sim.cancel_servers())

    def run_async_test(self, coro):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    def test_concurrent_payments(self):
        """
        Run concurrently PAYMENT operations of random tokens from client to servers which includes
        random faulty servers and some maximum delay which delays server messages.
        The test checks if all payment operations are successfully completed.
        """
        faulty_delay = 2
        iterations = 10

        async def test_logic():
            version = 1
            await self.server_sim.initialize_servers(simulate_faults=True, delay=faulty_delay)
            tasks = []
            for it in range(iterations):
                token_id = random.choice(range(1, TOTAL_TOKENS + 1))
                new_owner = random.choice(range(1, NUMBER_OF_CLIENTS + 1))
                version += 1
                tasks.append(asyncio.create_task(self.client.pay(token_id, version, new_owner)))

            results = await asyncio.gather(*tasks)
            # Check if all operations returned "OK"
            self.assertTrue(all(result == "OK" for result in results),
                            "Some payment operations did not complete successfully.")

        self.run_async_test(test_logic())


class TestGetTokensOperations(unittest.TestCase):

    def setUp(self):
        self.server_sim = ServerSimulation()
        self.client = Client()

    def tearDown(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.server_sim.cancel_servers())

    def run_async_test(self, coro):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    def test_concurrent_get_tokens(self):
        """
        Run concurrently GETTOKENS operations of random owners from client to servers which includes
        random faulty servers and some maximum delay which delays server messages.
        The test checks if all responses contains all the 10 tokens.
        """
        faulty_delay = 0
        iterations = 10

        async def test_logic():
            await self.server_sim.initialize_servers(simulate_faults=True, delay=faulty_delay)
            tasks = []
            for it in range(iterations):
                owner = random.choice(range(1, NUMBER_OF_CLIENTS + 1))
                tasks.append(asyncio.create_task(self.client.gettokens(owner)))

            results = await asyncio.gather(*tasks)
            # Check if all operations returned "OK"
            self.assertTrue(all(len(result) == INITIAL_TOKENS_PER_CLIENT for result in results),
                            "Some payment operations did not complete successfully.")

        self.run_async_test(test_logic())


class TestSafety(unittest.TestCase):

    def setUp(self):
        self.server_sim = ServerSimulation()
        self.client = Client()
        self.timeline = Timeline()

    def tearDown(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.server_sim.cancel_servers())

    def run_async_test(self, coro):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    async def perform_and_validate_operations(self, client: Client, timeline: list):
        """Perform operations and validate them against expected responses."""
        for index, (event, expected_response) in enumerate(timeline):
            actual_response = None
            if event['command'] == PAY_COMMAND:
                actual_response = await client.pay(token_id=event["id"], version=event['version'],
                                                   new_owner=event['new_owner'])
            elif event['command'] == GET_TOKENS_COMMAND:
                actual_response = await client.gettokens(owner=event['owner'])
            # Hash and compare responses to ensure consistency
            self.assertTrue(TestUtility.compare_states(expected_response, actual_response),
                            f"Operation {index} - {TestUtility.FAIL}")
            # print(f"Operation {index} - {TestUtility.PASS}")

    def test_main_safety(self):
        """
        Faulty Run: Initializes servers with faults and a specified delay, performs operations, and gathers the
        resulting states into faulty_states.

        Control Run: Re-initializes servers without faults and repeats the operations to gather control_states.

        State Comparison: Compares the state hashes from both runs to verify that despite faults,
        the system's end state remains consistent.

        Notice that we gather the operations responses instead operation requests in order to preserve
        linearizability.
        We check 2 things:
        1. We compare that the responses of each request are the same.
        2. The tokens distribution over clients is the same on both runs.
        :return:
        """
        faulty_delay = 1
        iterations = 5

        async def test_logic():
            # Faulty Run
            await self.server_sim.initialize_servers(simulate_faults=True, delay=faulty_delay)
            operations = generate_operations(iterations)
            await perform_operations(self.client, operations, self.timeline)
            faulty_states = await TestUtility.gather_states(self.client)
            faulty_hash = TestUtility.hash_state(faulty_states)
            await self.server_sim.cancel_servers()

            # Control Run
            await self.server_sim.initialize_servers(simulate_faults=False, delay=0)
            await self.perform_and_validate_operations(self.client, self.timeline.timeline)
            control_states = await TestUtility.gather_states(self.client)
            control_hash = TestUtility.hash_state(control_states)
            await self.server_sim.cancel_servers()

            # Compare states for safety verification
            self.assertTrue(faulty_hash == control_hash, TestUtility.FAIL)
            print(TestUtility.PASS)

        self.run_async_test(test_logic())


if __name__ == "__main__":
    unittest.main()

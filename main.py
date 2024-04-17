import asyncio
import aioconsole
import json
import math
import random
import sys
SERVERS = ['127.0.0.1:8889', '127.0.0.1:8890', '127.0.0.1:8891',
           '127.0.0.1:8892', '127.0.0.1:8893', '127.0.0.1:8894', '127.0.0.1:8895']
TOTAL_TOKENS = 60
MAX_SERVERS = 7
NUMBER_OF_CLIENTS = 6
NUMBER_OF_SERVERS = 7
INITIAL_SERVERS = 3
FAULTY_SERVERS = math.ceil(NUMBER_OF_SERVERS / 2) - 1
INITIAL_TOKENS_PER_CLIENT = TOTAL_TOKENS // NUMBER_OF_CLIENTS
PAY_COMMAND = "pay"
GET_TOKENS_COMMAND = "gettokens"


class TokenManager:
    def __init__(self):
        self.tokens = [(i, 1, math.ceil(i / INITIAL_TOKENS_PER_CLIENT)) for i in range(1, TOTAL_TOKENS + 1)]
        self.lock = asyncio.Lock()

    def apply_update(self, token_id, version, new_owner):
        # async with self.lock:
        for i, token in enumerate(self.tokens):
            if token[0] == token_id and token[1] < version:
                self.tokens[i] = (token_id, version, new_owner)
                return True
        return False

    def get_token_by_id(self, token_id):
        # async with self.lock:
        return self.tokens[token_id - 1]


class CommunicationHandler:
    """
    Deals with sending and receiving messages.
    """
    @staticmethod
    async def read_message(reader):
        data = await reader.read(1024)
        message = data.decode()
        return message

    @staticmethod
    async def write_message(writer, message):
        # self.writer_lock = asyncio.Lock()
        encoded_message = message.encode()
        writer.write(encoded_message)
        await writer.drain()


class Server:
    def __init__(self, token_manager, simulate_faults=False, delay=0):
        self.token_manager = token_manager
        self.server = None
        self.server_commands = {
            'transform': self.transform_to_client,
            'quit': self.close_server,
            'help': self.print_help
        }
        self.simulate_faults = simulate_faults
        self.delay = delay

    async def run(self):
        task1 = asyncio.create_task(self.start_server())
        task2 = asyncio.create_task(self.input_listener())
        await asyncio.gather(task1, task2)

    async def handle_client(self, reader, writer):
        request = json.loads(await CommunicationHandler.read_message(reader))
        command = request["command"]
        response = ""

        # Simulate omission or delay
        if self.delay > 0:
            await asyncio.sleep(random.uniform(0, self.delay))  # Simulate network delay
        if self.simulate_faults and random.choice([True, False]):
                # drop requests to simulate omissions
                writer.close()
                return

        if command == PAY_COMMAND:
            token_id, version, new_owner = request["id"], request["version"], request["new_owner"]
            self.token_manager.apply_update(token_id, version, new_owner)
            response = json.dumps({"response": "OK"})

        elif command == GET_TOKENS_COMMAND:
            token_id = request["id"]
            token = self.token_manager.get_token_by_id(token_id)
            response = json.dumps({"id": f"{token[0]}", "version": f"{token[1]}", "owner": f"{token[2]}"})
        if self.delay > 0:
            await asyncio.sleep(random.uniform(0, self.delay))  # Simulate network delay
        if self.simulate_faults and random.choice([True, False]):
            # drop requests to simulate omissions
            writer.close()
            return
        await CommunicationHandler.write_message(writer, response)
        writer.close()
        # await writer.wait_closed()  # Wait until the connection is fully closed

    async def close_server(self):
        self.server.close()
        await self.server.wait_closed()
        # print("Server closed.")

    async def transform_to_client(self):
        await self.close_server()
        client = Client()
        await client.run_client()

    async def print_help(self):
        # print("\033[H\033[J", end="")  # ANSI escape codes to clear the screen (works on UNIX-like systems)
        print("Server UI commands:")
        print("  transform  - Convert the server into a client mode.")
        print("  quit       - Shut down the server.")
        print("  help       - Display this help message.\n")

    async def input_listener(self):
        # Delay for command menu to appear after server connection output.
        await asyncio.sleep(0.1)
        await self.print_help()
        while True:
            cmd = (await aioconsole.ainput(">> ")).strip().lower()
            if cmd in self.server_commands:
                await self.server_commands[cmd]()
                if cmd == "quit":
                    break
            else:
                print("Unknown command. Type 'help' for a list of commands.")

    async def start_server(self, port=8889):
        try:
            self.server = await asyncio.start_server(self.handle_client, '127.0.0.1', port)
            addr = self.server.sockets[0].getsockname()
            # print(f'Serving on {addr}')
            async with self.server:
                try:
                    await self.server.serve_forever()
                except asyncio.CancelledError:
                    pass  # Expected on server.close()

        except OSError as e:
            # print(f'Could not start server on port {port}. Error: {e}')
            await self.start_server(port + 1)  # Try the next port

    def start_process_server(self, port, start_event):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.server = asyncio.start_server(self.handle_client, '127.0.0.1', port)

        server = loop.run_until_complete(self.server)

        # Signal that the server is ready
        start_event.set()

        try:
            loop.run_forever()
        finally:
            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()

class Client:
    """
    Manages client-side interactions.
    """
    def __init__(self):
        self.servers = SERVERS
        self.honest_servers = math.floor(NUMBER_OF_SERVERS / 2) + 1

    async def transform_to_server(self):
        # server = Server(1)
        server = Server(token_manager=TokenManager)
        await server.run()

    async def send_request_to_server(self, server_address, request, curr_servers, first=True):
        host, port = server_address.split(':')
        writer = None  # Ensure writer is defined in the scope of the function
        try:
            reader, writer = await asyncio.open_connection(host, int(port))
            await CommunicationHandler.write_message(writer, json.dumps(request))
            response = await CommunicationHandler.read_message(reader)
            return response

        except ConnectionRefusedError as e:
            # Handle specific error, e.g., connection refused
            curr_servers[0] -= 1  # Properly handle server count decrement

        except Exception as e:
            # Handle other general exceptions
            print(f"Error connecting to {server_address}: {e}")
            # Optional: Depending on your design, you might want to handle retry logic here

        finally:
            # Only attempt to close if 'writer' was successfully created
            if writer is not None:
                writer.close()

    async def broadcast_request_gettokens(self, request):
        curr_servers = [7]

        tasks = [asyncio.create_task(self.send_request_to_server(server, request, curr_servers))
                 for server in self.servers]

        token_id = request["id"]
        counter = 0
        maximum_version = -math.inf
        max_owner = None
        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                result = await task
                if not result:
                    continue
                result = json.loads(result)
                counter += 1
                version = int(result["version"])
                owner = int(result["owner"])
                if version > maximum_version:
                    maximum_version = version
                    max_owner = owner
                if counter > math.floor(curr_servers[0] / 2):
                    # Cancel any remaining tasks
                    for t in pending:
                        t.cancel()
                    await self.pay(token_id, maximum_version, max_owner)
                    return {"id": token_id, "version": maximum_version, "owner": max_owner}
            tasks = list(pending)  # Update tasks for the next iteration
        raise Exception("Request failure")

    async def broadcast_request_pay(self, request):
        curr_servers = [len(self.servers)]
        tasks = [asyncio.create_task(self.send_request_to_server(server, request, curr_servers))
                 for server in self.servers]

        counter = 0
        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                await task
                counter += 1
                if counter >= (curr_servers[0] // 2) + 1:
                    # Cancel any remaining tasks
                    for t in pending:
                        t.cancel()
                    return
            tasks = list(pending)  # Update tasks for the next iteration

    async def pay(self, token_id, version, new_owner):
        request = {"command": PAY_COMMAND, "id": token_id, "version": version, "new_owner": new_owner}
        await self.broadcast_request_pay(request)
        return "OK"

    async def gettokens(self, owner):
        response = []
        all_tokens = list(range(1, TOTAL_TOKENS + 1))
        batch_size = 6  # Number of requests to process concurrently

        # Process in batches of 6
        for i in range(0, len(all_tokens), batch_size):
            batch_tokens = all_tokens[i:i + batch_size]
            tasks = [self.broadcast_request_gettokens({"command": GET_TOKENS_COMMAND, "owner": owner, "id": token_id})
                     for token_id in batch_tokens]
            results = await asyncio.gather(*tasks)

            for result in results:
                if not result:
                    continue  # If a request fails, optionally handle it or ignore
                if result["owner"] == owner:
                    response.append((result['id'], result['version']))

        return response

    async def check_server_connections(self, servers=SERVERS):
        status_results = {}
        for server in servers:
            try:
                # Split the server address into host and port
                host, port = server.split(':')
                # Attempt to open a connection
                reader, writer = await asyncio.open_connection(host, int(port))
                # If connection is successful, close the writer and mark as Connected
                writer.close()
                await writer.wait_closed()
                status_results[server] = 'Connected'
            except (ConnectionRefusedError, Exception) as e:
                status_results[server] = 'Failed to Connect'
        return status_results

    def help_message(self):
        print("Client UI commands:")
        print("  pay <tokenid,version,newowner>  - Send payment or transfer ownership of a token.")
        print("  gettokens <ownerid>             - Retrieve tokens based on ownership.")
        print("  check                           - Verify connectivity with all servers.")
        print("  transform                       - Convert this client node into a server.")
        print("  help                            - Display this help message.")
        print("  quit                            - Exit the client interface.\n")

    async def run_client(self):
        # Clear the screen for better clarity
        # print("\033[H\033[J", end="")  # ANSI escape codes to clear the screen (works on UNIX-like systems)
        self.help_message()
        while True:
            user_input = (await aioconsole.ainput(">> ")).strip().lower()
            commands = user_input.split()

            # Extract the command and parameters
            if len(commands) == 0:
                continue

            main_command = commands[0]

            if main_command == 'quit':
                print("Exiting...")
                break
            if main_command == "help":
                self.help_message()

            elif main_command == 'check':
                print("Checking server connections...")
                connection_status = await self.check_server_connections(self.servers)
                for server, status in connection_status.items():
                    print(f"{server}: {status}")

            elif main_command == 'transform':
                print("Transforming this node to a server...")
                await self.transform_to_server()
                print("Node transformed successfully.")

            elif main_command in ['pay', 'gettokens']:
                if len(commands) < 2:
                    print(f"Invalid command format for {main_command}. Please check the format and try again.")
                    continue

                try:
                    # Assume parameters are comma-separated
                    params = commands[1].split(',')
                    if main_command == 'pay':
                        if len(params) != 3:
                            print("Usage: pay <tokenid,version,newowner>")
                            continue
                        token_id, version, new_owner = map(int, params)
                        payment_response = await self.pay(token_id, version, new_owner)
                        print(f"{payment_response}")

                    elif main_command == 'gettokens':
                        if len(params) != 1:
                            print("Usage: gettokens <ownerid>")
                            continue
                        owner = int(params[0])
                        response = await self.gettokens(owner)
                        print(f"{response}")

                except ValueError:
                    print("Error: All inputs must be integers. Please check your input and try again.")
                except Exception as e:
                    print(f"An error occurred: {str(e)}")

            else:
                print("Unknown command. Please try again.")


async def main():
    if len(sys.argv) < 2:
        print("Usage: main.py server | client")
        return

    mode = sys.argv[1]
    token_manager = TokenManager()
    if mode == "server":
        server = Server(token_manager)
        await server.run()

    elif mode == "client":
        client = Client()
        await client.run_client()
    else:
        print("Unknown mode. Use 'server' or 'client'.")


if __name__ == "__main__":
    asyncio.run(main())

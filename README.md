# Distributed Token Management System

The Distributed Token Management System is an asyncio-based Python application designed to manage and facilitate token transactions across a network of clients and servers. It allows users to execute token transactions, retrieve token ownership information, and seamlessly transition between client and server roles within a distributed architecture.

## Features

- **Token Transactions**: Execute payments and transfer token ownership.
- **Token Retrieval**: Retrieve detailed information about token ownership based on user IDs.
- **Dynamic Role Transformation**: Seamlessly transition between client and server functionalities to maintain network flexibility and efficiency.
- **Server Management**: Manage server operations with intuitive command-line interfaces.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

What things you need to install the software and how to install them:

```bash
Python 3.7+
```
### Installing
A step by step series of examples that tell you how to get a development environment running:
1. Clone the repository:


```bash
git clone https://github.com/yourusername/distributed-token-management.git
```
2. Navigate to the project directory:
```bash
cd distributed-token-management
```
3. Install necessary packages:
```bash 
pip install -r requirements.txt
```
4. Run some server:
```bash
python main.py server
```
5. Run some client:
```bash
python main.py client
```
## Usage
### Client Commands
- **Pay: pay <tokenid,version,newowner>**
Send payment or transfer ownership of a token.
- **Get Tokens: gettokens <owner,>** Retrieve tokens based on ownership.
- **Check: check** Verify connectivity with all servers.
- **Transform: transform** Convert the client node into a server.
- **Help: help** Display available commands.
### Server Commands
- **Transform: transform** Convert the server into a client mode.
- **Quit: quit** Safely shut down the server.
- **Help: help** Display available commands.

## Testing
This project uses unittest for testing its components. To run tests, navigate to the project directory and execute the following:

```bash
python -m unittest discover -s tests
```
## Authors
- Yosef Edery - yosefede06


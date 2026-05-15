# Assignment 01 — Custom Container Orchestrator

A lightweight container orchestrator built in Python, designed to manage containerized workloads with self-healing, cluster management, port mapping, and environment variable support.

---

## Features

| Feature | Status |
|---|---|
| Self-healing | ✅ Implemented |
| Cluster management | ✅ Implemented |
| Port mapping | ✅ Implemented |
| Environment variable passing | ✅ Implemented |
| Secrets management (Base64 encoding) | 🔜 Planned |
| AWS Vault integration | 🔜 Planned |

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- Python 3.x

---

### Running Locally

**1. Clone the repository**

```bash
git clone <your-repo-url>
cd <repo-directory>
```

**2. Install Docker and add your user to the Docker group**

```bash
sudo usermod -aG docker $USER
newgrp docker
```

**3. Build the Docker image**

```bash
docker build -t orch-app:latest .
```

**4. Set up the Python environment**

```bash
python -m venv venv
source ./venv/bin/activate        # Linux / macOS
# source ./venv/Scripts/activate  # Windows
```

**5. Run the orchestrator**

```bash
python orch.py -f app.yml
```

---

### Automated Deployment (CI/CD)

To deploy automatically using a self-hosted GitHub Actions runner:

**1. Configure GitHub repository secrets**

Go to your repository → **Settings** → **Secrets and variables** → **Actions**, and add any required environment variables.

**2. Set up your self-hosted runner**

Follow the [GitHub documentation](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners) to register and configure your runner machine.

**3. Prepare the runner environment**

On the runner machine, ensure the following are installed and configured:

```bash
# Install Python and create a virtual environment
python -m venv venv
source ./venv/bin/activate

# Install Docker and add runner user to Docker group
sudo usermod -aG docker $USER
newgrp docker
```

The pipeline will handle the rest on each push.

---

## Project Structure

```
.
├── orch.py       # Main orchestrator entry point
├── app.yml       # Application configuration file
├── Dockerfile    # Container image definition
└── README.md
```

---

## Roadmap

- [ ] **Secrets management** — Secure secret injection using Base64 encoding
- [ ] **AWS Vault integration** — Fetch and inject secrets from HashiCorp Vault on AWS


Implementation plan for secret management

for normal secret management I will put a base64 decoder in the python app

for aws vault integration 
we will first create the iam role in aws the put the creds into my python code and use it to fetch tha secrets accordingly to the yml file.
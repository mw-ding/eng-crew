# Lab test host image (M20.1 lab B, #1356): the multi-device design, Remote acceptance criteria and the local lab.
# Build from the repo root: docker build -f environments/terminal/remote/lab/Dockerfile --build-arg LAB_BASE=<ref> .
# LAB_BASE is the owner-approved ARM64 Linux image, already preloaded and pinned by digest (name@sha256:<64 hex>),
# holding Python 3.11+, git, tmux, the OpenSSH server and procps. Nothing is downloaded or installed here.
# The version check asks for 3.11, what crew-install.py needs: it extracts on 3.11.0 to 3.11.3 too (#1447).
# Host keys the base carried are deleted; each container makes its own at first start (crew-lab-host.py supervise).
# /etc/mdstack/supervised selects the linux host OS adapter's supervised mode: this image has no systemd.
ARG LAB_BASE
FROM ${LAB_BASE}
ARG LAB_BASE
RUN python3 -c "import re, sys; sys.exit(not re.fullmatch(r'[^@\s]+@sha256:[0-9a-f]{64}', sys.argv[1]))" "$LAB_BASE" \
 && python3 -c "import sys; sys.exit(sys.version_info < (3, 11))" \
 && command -v git tmux ps ssh-keygen /usr/sbin/sshd \
 && useradd --create-home --shell /bin/sh crew && usermod -p '*' crew \
 && rm -rf /etc/ssh/ssh_host_* /etc/ssh/crew-lab \
 && mkdir -p /etc/mdstack && echo crew-lab-host.py > /etc/mdstack/supervised
COPY scripts/crew-install.py /usr/local/lib/mdstack-lab/scripts/crew-install.py
COPY environments/terminal/remote/lab/crew-lab-host.py /usr/local/lib/mdstack-lab/environments/terminal/remote/lab/
COPY environments/terminal/remote/lab/sshd_config /etc/ssh/crew-lab.conf
HEALTHCHECK --interval=10s CMD ["python3", "/usr/local/lib/mdstack-lab/environments/terminal/remote/lab/crew-lab-host.py", "ready", "--user", "crew"]
ENTRYPOINT ["python3", "/usr/local/lib/mdstack-lab/environments/terminal/remote/lab/crew-lab-host.py", "supervise", "--user", "crew"]

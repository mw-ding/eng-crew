# Lab base image (M20.1 lab B2, #1430): the LAB_BASE the lab Dockerfile beside it builds on.
# Official Debian 12 slim, pinned by its linux/arm64 manifest digest; bookworm's python3 is 3.11.
# It installs only Python 3, git, tmux, the OpenSSH server and procps, and deletes the host keys the
# openssh-server package makes. No key, credential or token is copied in.
# Build and pin: see the local lab section of the multi-device runtime doc.
FROM debian:bookworm-slim@sha256:ec8534cda2cb30f29f44f23e135297af7a1496f2990fd8e4e84aa36b081a757a
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 git tmux openssh-server procps \
 && rm -rf /var/lib/apt/lists/* /etc/ssh/ssh_host_*

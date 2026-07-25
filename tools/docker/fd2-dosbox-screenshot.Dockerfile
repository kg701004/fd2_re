# Headless, reproducible screenshot oracle for the user-owned FD2 DOS build.
# The game directory and captures are supplied as mounts at runtime; neither
# original game data nor screenshots are baked into this image.
FROM demwin-dosbox:latest

COPY tools/docker/fd2-dosbox-screenshot.sh /usr/local/bin/fd2-dosbox-screenshot
RUN chmod 0755 /usr/local/bin/fd2-dosbox-screenshot

ENTRYPOINT ["/usr/local/bin/fd2-dosbox-screenshot"]

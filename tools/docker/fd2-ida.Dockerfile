# Local FD2 reverse-engineering overlay for the user-authorized IDA Pro image.
#
# Build only after `/home/anr2/ida_94_official/dist` has built `ida-pro:9.4`
# from the user's official installer.  This image deliberately contains no
# installer,
# game binary, IDA database, or license; the license is mounted read-only at
# runtime and the private IDA home volume keeps idapyswitch's selection.
FROM ida-pro:9.4

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 libpython3.12 \
    && rm -rf /var/lib/apt/lists/*

USER ida

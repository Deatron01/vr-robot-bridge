# Environment Setup Log

## Why WSL2 and not native Windows

irob-saf requires ROS Noetic + the da Vinci Research Kit (dVRK 2.2.1) +
cisst-saw, which upstream only supports on Linux (Ubuntu 20.04) or via the
official Docker image. There is no native-Windows build. WSL2 gives a real
Ubuntu 20.04 userland on this PC without dual-booting or a VM.

## What was done (2026-09-12)

1. **WSL2 distro import.** Ubuntu 20.04 ("focal") was removed from the WSL
   online catalog (`wsl --install -d Ubuntu-20.04` no longer works), so the
   distro was imported manually from Canonical's cloud image:
   ```powershell
   curl.exe -L -o C:\WSL\ubuntu-20.04-rootfs.tar.xz `
     https://cloud-images.ubuntu.com/releases/20.04/release/ubuntu-20.04-server-cloudimg-amd64-root.tar.xz
   wsl --import Ubuntu-20.04 C:\WSL\Ubuntu-20.04 C:\WSL\ubuntu-20.04-rootfs.tar.xz --version 2
   ```
   A non-root sudo user `nipit` was created and set as the distro default via
   `/etc/wsl.conf` (cloud images boot as root and have no default user).
   `cloud-init` was purged (not needed under WSL, slows boot).

2. **ROS Noetic.** Installed `ros-noetic-desktop-full` from the official ROS
   apt repo (key dearmored from `ros.asc`, not the raw armored file — the
   `signed-by=` keyring must be binary). `rosdep init` + `rosdep update` run.
   Build tools: `python3-catkin-tools`, `python3-rosinstall`, `python3-vcstool`,
   `build-essential`, `libeigen3-dev`, `git`.

3. **irob-saf dependency stack**, following the steps baked into
   `irob-saf`'s own `Dockerfile` (adapted from Docker to a plain WSL2 shell):
   - Added the librealsense apt repo (its signing key had rotated since the
     Dockerfile was written — see `keyserver.ubuntu.com --recv-key
     FB0B24895113F120` — the ID in the Dockerfile, `...C8B3A55A6F3EFCDE`, is a
     different/older librealsense key and was imported too but wasn't the one
     actually needed for the current repo signature).
   - Installed the long apt dependency list from the Dockerfile
     (librealsense, Qt, OpenIGTLink, ncurses, vcstool, etc.)
   - `pip3 install` the Python deps (numpy, scipy, matplotlib, jupyter, ...)
   - Built **libnabo** and **libpointmatcher** from source (`cmake` +
     `make` + `sudo make install`) — the apt-packaged
     `ros-noetic-libpointmatcher` alone isn't what `ethzasl_icp_mapping`
     links against here.
   - `~/catkin_ws`: `catkin init`, cloned `ethzasl_icp_mapping`, then
     `vcs import --recursive --input
     https://raw.githubusercontent.com/jhu-saw/vcs/main/ros1-dvrk-2.2.1.vcs`
     to pull `cisst-saw`, `crtk`, and `dvrk` (dVRK 2.2.1) into `src/`.
   - `catkin build --summary` — **all 45 packages built, 0 failures**
     (~8 minutes).
   - `catkin build irob-saf` — **all 8 irob-saf packages built, 0 failures**.
   - Cloned `OE-daVinci` config/calibration files into
     `cisst-saw/sawIntuitiveResearchKit/share/`.

4. Verified: `rospack find irob_msgs` / `irob_motion` resolve correctly from
   a fresh shell (`.bashrc` sources `devel/setup.bash` and
   `devel/cisstvars.sh` automatically).

## Useful commands

```powershell
# From Windows (PowerShell)
wsl -d Ubuntu-20.04                  # open a shell in the distro
wsl --list --verbose                 # check distro status
```

```bash
# Inside Ubuntu-20.04
cd ~/catkin_ws
catkin build                         # rebuild everything
catkin build irob-saf                # rebuild just irob-saf
roscd irob_motion                    # jump to a package
```

## Known gaps / not yet done

- No real dVRK hardware or MTM/PSM console has been launched — this is a
  build-only verification, not a runtime/hardware check.
- `librealsense2-dkms` tried to build a kernel module for a kernel WSL2
  doesn't run (`5.4.0-216-generic`); this is expected/harmless under WSL2
  (no physical RealSense camera passthrough) and did not block the apt
  install.
- Gazebo/MoveIt simulation (needed for the VR-telemetry bridge itself, per
  `implementation_plan.md`) has not been set up yet — that's the next stage.

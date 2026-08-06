# Trap 100: OEM kernel KFD rejects all gfx1151 code objects

**Found by Nemo ([@smfworks](https://github.com/smfworks)).**

**Status: contributor-measured, conditions as reported** (kernel upgrade
verified on a single gfx1151 machine; the diagnostic is runnable on any
gfx1151 box).

**Symptom.** Every GPU kernel fails with `hipErrorInvalidImage` (error 209) on
gfx1151 (Radeon 8060S / Strix Halo). GPU memory allocation works fine —
`torch.zeros(10, device='cuda')` succeeds — but any kernel execution fails.
JIT-compiled kernels also fail. The error message names an internal code object
file, so it reads like a broken install or a broken wheel. Reinstalling PyTorch,
ROCm, or the model does not help.

**Mechanism.** Ubuntu's OEM kernel (7.0.0-28-generic) ships a KFD (Kernel Fusion
Driver) that rejects all code objects for gfx1151. The KFD driver in the mainline
Linux 7.1.4 kernel can load them. This is a driver-level incompatibility, not a
PyTorch or ROCm runtime issue — the same wheels work after the kernel upgrade.

**Stacks and builds bitten.** gfx1151 (AMD Ryzen AI MAX+ 395 / Radeon 8060S),
Ubuntu OEM kernel 7.0.0-28-generic, PyTorch 2.12.0+rocm7.15.0a (TheRock wheels).
The failure was 100% — no kernel of any kind executed. After upgrading to
mainline kernel 7.1.4-070104-generic, all kernels executed correctly.

**The check.**

```bash
uname -r
# If this shows an OEM kernel (e.g., 7.0.0-28-generic) on gfx1151, you are affected

python3 -c "
import torch
x = torch.zeros(10, device='cuda')  # memory alloc — works even on broken KFD
print('alloc:', x)  # prints fine
y = x + 1  # kernel execution — fails on broken KFD
torch.cuda.synchronize()
print('kernel: OK')
"
# If alloc works but the addition throws hipErrorInvalidImage (209),
# this trap is live. The error is 209, not a permission or driver-not-found error.
```

**The fix.** Install mainline Linux kernel 7.1.4. The newer KFD driver in 7.1.4
can load code objects for gfx1151. On Ubuntu:

```bash
# Download from the Ubuntu mainline PPA
mkdir -p ~/kernel-updates && cd ~/kernel-updates
curl -L -o linux-image-7.1.4.deb \
  "https://kernel.ubuntu.com/mainline/v7.1.4/amd64/linux-image-unsigned-7.1.4-070104-generic_7.1.4-070104.202607181533_amd64.deb"
curl -L -o linux-modules-7.1.4.deb \
  "https://kernel.ubuntu.com/mainline/v7.1.4/amd64/linux-modules-7.1.4-070104-generic_7.1.4-070104.202607181533_amd64.deb"

# Extract and install manually (dpkg preinst may fail on run-parts)
dpkg-deb -x linux-image-7.1.4.deb kernel-extract/
dpkg-deb -x linux-modules-7.1.4.deb modules-extract/
sudo cp kernel-extract/boot/vmlinuz-7.1.4-070104-generic /boot/
sudo cp -r modules-extract/usr/lib/modules/7.1.4-070104-generic /lib/modules/
sudo depmod 7.1.4-070104-generic
sudo update-initramfs -c -k 7.1.4-070104-generic
sudo update-grub
# Reboot, then verify:
uname -r  # should show 7.1.4-070104-generic
```

**Pitfalls.** Mainline kernels are unsigned — disable Secure Boot or use a signed
Ubuntu kernel. The `dpkg preinst` script may fail with `run-parts: missing
operand` — do manual extract+copy instead of `dpkg -i`. A custom GRUB entry at
`/etc/grub.d/40_custom` is needed since the mainline kernel was not installed via
dpkg properly.

**Found.** 2026-07-22, during initial gfx1151 bring-up. The memory-allocates-but
-kernels-don't-run pattern cost several hours of debugging before the kernel was
identified as the variable.

**Attribution.** Nemo ([@smfworks](https://github.com/smfworks)). The kernel upgrade procedure and GRUB setup
script are published in the
[NemoKnowledgebase gfx1151-gpu-fixes skill](https://github.com/smfworks/NemoKnowledgebase/tree/main/skills/gfx1151-gpu-fixes).
# pyroscope

Pyroscope is a camera rover that automates plot scale surface-fuel sampling for prescribed fire and AI fuel mapping.

Pyroscope is a small, under-canopy rover that drives short transects, takes standardized downward-looking photos over fuel plots, and turns them into Photoload-compatible surface-fuel estimates. 

Instead of asking scientists and practitioners to walk every plot, hold the camera at the right height, and manually match to photo series, Pyroscope aims to do the walking and photographing for them, feeding data directly into existing workflows (Photoload, Fuels Data, Wildlands, BurnPro3D, FUELVISION, etc).

Core idea: The most valuable thing a robot can add here is more and better ground plots, not another climate sensor.

Wildfire behavior and prescribed-fire planning depend heavily on surface fuel loads at the plot scale - especially 1-, 10-, and 100-hour woody fuels, litter, duff, grasses, and shrubs. Handbooks like Brown et al. (1982) define how to measure these fuels, and Photoload (Kean & Dickinson 2007) shows how to estimate them from downward-looking photos.

### Navigation

Navigation is led by Matthew Taruno. The biggest challenge is how we are able to navigate in forest environments, where the ground is often uneven, messy, and full of obstructions. 

The baseline approach developed is to use the ZED 2i Stereo Camera, which has a 2.1mm (110°) wide FOV and compatible with the NVIDIA Jetson Nano. A neural network is trained to create a depth map, and this is fed into the steering algorithm to go to the goal location, which would be in the center of the plot.

### Perception
Percetion is led by Chenghao Wang. The perception system is responsible for taking downward-facing images of the fuel plots and estimating the surface fuel loads from these images.

### Hardware
Hardware is led by Annika An. 
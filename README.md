# Beach Simulator

A 2D particle-based water physics simulator built with pygame and Pymunk. Watch as an oscillating wave generator pushes water particles across a sandy slope.

## Features

- **Particle-Based Water Physics**: Realistic water simulation using Pymunk 2D physics engine
- **Oscillating Wave Generator**: An invisible wall moves back and forth with sinusoidal motion to create waves
- **Adjustable Wave Speed**: UI slider to control wave oscillation frequency in real-time
- **Sand Slope**: Water particles interact with a diagonal sand surface

## Requirements

- Python 3.7+
- pygame 2.5.0+
- pymunk 7.0+

## Installation

1. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running

```bash
python beach_simulator.py
```

## Controls

- **Wave Speed Slider**: Click and drag to adjust oscillation frequency (0.05 - 1.0 Hz)
- **R**: Reset particles
- **ESC** or close window: Exit the simulator

## How It Works

1. **Particle System**: Water is represented as hundreds of small circular particles
2. **Pymunk Physics**: Each particle has mass, friction, and elasticity properties
3. **Wave Generator**: A kinematic wall on the right side oscillates with sinusoidal motion
4. **Collision Detection**: Particles collide with each other, the sand slope, and boundaries
5. **Wave Propagation**: As the wall pushes particles, the compression propagates through the water

## Configuration

Key parameters in `beach_simulator.py`:

- `PARTICLE_RADIUS`: Size of water particles (default: 2.5)
- `PARTICLE_MASS`: Mass of each particle (default: 0.5)
- `WAVE_WALL_AMPLITUDE`: How far the wave wall travels (default: 40 pixels)
- `WAVE_WALL_FREQUENCY`: Default oscillation speed (default: 0.25 Hz)
- `GRAVITY`: Downward acceleration (default: 900)

## Future Enhancements

- Mouse interaction to pick up and move sand/water
- Sand smoothing when waves lap across it

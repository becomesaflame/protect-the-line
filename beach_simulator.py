"""
Beach Simulator using Pymunk for 2D physics
"""
import pygame
import pymunk
import pymunk.pygame_util
import math
import random

# Initialize Pygame
pygame.init()

# Window constants
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
FPS = 60

# Colors
SAND_COLOR = (238, 203, 173)
WATER_COLOR = (64, 164, 223)
SKY_COLOR = (135, 206, 235)

# Physics parameters
GRAVITY = 900
PARTICLE_RADIUS = 2.5
PARTICLE_MASS = 0.5
PARTICLE_FRICTION = 0.07
PARTICLE_ELASTICITY = 0.05

# Sand slope definition
SAND_LEFT_Y = WINDOW_HEIGHT * (1/3)  # 2/3 from top
SAND_RIGHT_Y = WINDOW_HEIGHT - 50     # Near bottom

# Sand texture parameters
SAND_BUMP_COUNT = 40  # Number of bump points along the surface
SAND_BUMP_HEIGHT = 15  # Maximum random bump height (pixels)

# Water fill area
WATER_FILL_TOP = WINDOW_HEIGHT * 0.35  # Higher water level (lower number = more water)

# Wave generator parameters (oscillating wall)
WAVE_WALL_THICKNESS = 20  # Much thicker to prevent tunneling

# Fast wave (primary oscillation)
WAVE_FAST_AMPLITUDE = 40  # How far the wall moves left/right
WAVE_FAST_FREQUENCY = 0.25  # Oscillations per second (Hz)

# Slow wave (secondary oscillation - creates longer swells)
WAVE_SLOW_AMPLITUDE = 120  # 3x the fast wave amplitude
WAVE_SLOW_PERIOD = 10.0  # Default period in seconds (frequency = 1/period)

# Base position needs to accommodate both amplitudes
WAVE_WALL_BASE_X = WINDOW_WIDTH - 40 - WAVE_SLOW_AMPLITUDE  # Start further right

# Collision types
COLLISION_WATER = 1
COLLISION_BOUNDARY = 2
COLLISION_SAND = 3
COLLISION_WAVE_WALL = 4

# Collision categories (bitmask for filtering)
CAT_WATER = 0b0001
CAT_SAND = 0b0010
CAT_BOUNDARY = 0b0100
CAT_WAVE_WALL = 0b1000

# Collision masks (what each category collides with)
# Water collides with everything
MASK_WATER = CAT_WATER | CAT_SAND | CAT_BOUNDARY | CAT_WAVE_WALL
# Sand collides with water, sand, boundary - NOT wave wall
MASK_SAND = CAT_WATER | CAT_SAND | CAT_BOUNDARY
# Boundary collides with everything
MASK_BOUNDARY = CAT_WATER | CAT_SAND | CAT_BOUNDARY | CAT_WAVE_WALL
# Wave wall only collides with water
MASK_WAVE_WALL = CAT_WATER

# Sand particle parameters
SAND_PARTICLE_RADIUS = 2.5
SAND_PARTICLE_MASS = 2.0  # Heavier than water
SAND_PARTICLE_FRICTION = 0.9  # High friction
SAND_PARTICLE_ELASTICITY = 0.05
SAND_PARTICLE_SPACING = SAND_PARTICLE_RADIUS * 2.5
SAND_LAYERS = 8  # Number of layers of sand particles below surface

# Erosion/deposition parameters
SANDINESS_MIN = 0
SANDINESS_MAX = 10
PICKUP_PROB_MIN = 0.003  # 30% per second at high sandiness (per frame: /60)
PICKUP_PROB_MAX = 0.005  # 50% per second at low sandiness
DEPOSIT_PROB_MIN = 0.003  # 30% per second at low sandiness
DEPOSIT_PROB_MAX = 0.005  # 50% per second at high sandiness


class Slider:
    """Simple UI slider control"""
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.dragging = False
        
        # Colors
        self.bg_color = (200, 200, 200)
        self.fg_color = (100, 150, 200)
        self.handle_color = (50, 100, 150)
        self.text_color = (0, 0, 0)
        
        # Handle
        self.handle_width = 12
        self.handle_rect = self._get_handle_rect()
    
    def _get_handle_rect(self):
        """Calculate handle position based on current value"""
        t = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.rect.x + t * (self.rect.width - self.handle_width)
        return pygame.Rect(handle_x, self.rect.y - 2, self.handle_width, self.rect.height + 4)
    
    def _value_from_x(self, x):
        """Calculate value from x position"""
        t = (x - self.rect.x) / self.rect.width
        t = max(0, min(1, t))
        return self.min_val + t * (self.max_val - self.min_val)
    
    def handle_event(self, event):
        """Handle mouse events, return True if value changed"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.handle_rect.collidepoint(event.pos) or self.rect.collidepoint(event.pos):
                    self.dragging = True
                    self.value = self._value_from_x(event.pos[0])
                    self.handle_rect = self._get_handle_rect()
                    return True
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False
        
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.value = self._value_from_x(event.pos[0])
                self.handle_rect = self._get_handle_rect()
                return True
        
        return False
    
    def draw(self, screen):
        """Draw the slider"""
        font = pygame.font.Font(None, 20)
        
        # Draw label
        label_text = font.render(f"{self.label}: {self.value:.2f}", True, self.text_color)
        screen.blit(label_text, (self.rect.x, self.rect.y - 18))
        
        # Draw background track
        pygame.draw.rect(screen, self.bg_color, self.rect, border_radius=3)
        
        # Draw filled portion
        t = (self.value - self.min_val) / (self.max_val - self.min_val)
        filled_width = int(t * self.rect.width)
        filled_rect = pygame.Rect(self.rect.x, self.rect.y, filled_width, self.rect.height)
        pygame.draw.rect(screen, self.fg_color, filled_rect, border_radius=3)
        
        # Draw handle
        pygame.draw.rect(screen, self.handle_color, self.handle_rect, border_radius=2)


class BeachSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Pymunk Beach Simulator")
        self.clock = pygame.time.Clock()
        self.running = True
        self.time = 0.0
        
        # Create pymunk space
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)
        
        # Calculate sand gravity direction (normal to average slope)
        # Average slope goes from (0, SAND_LEFT_Y) to (WINDOW_WIDTH, SAND_RIGHT_Y)
        slope_dx = WINDOW_WIDTH
        slope_dy = SAND_RIGHT_Y - SAND_LEFT_Y
        slope_len = math.sqrt(slope_dx**2 + slope_dy**2)
        # Normal to slope (perpendicular, pointing "into" the sand)
        self.sand_gravity_dir = (slope_dy / slope_len, -slope_dx / slope_len)
        # Make sure it points generally downward
        if self.sand_gravity_dir[1] < 0:
            self.sand_gravity_dir = (-self.sand_gravity_dir[0], -self.sand_gravity_dir[1])
        
        # Reduce collision iterations for performance
        self.space.iterations = 10
        
        # Sand and water particle tracking
        self.sand_bodies = []
        self.sand_shapes = []
        self.water_sandiness = {}  # Maps water body to sandiness value
        
        # Create boundaries and particles
        self.create_boundaries()
        self.create_sand_particles()
        self.create_wave_generator()
        self.create_water_particles()
        
        # Set up collision handler for water-sand interaction
        self.setup_collision_handlers()
        
        # Debug draw options (optional)
        self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)
        
        # UI controls
        self.fast_freq_slider = Slider(
            x=10, y=100, width=150, height=10,
            min_val=0.05, max_val=1.0,
            initial_val=WAVE_FAST_FREQUENCY,
            label="Fast Wave Speed"
        )
        self.wave_fast_frequency = WAVE_FAST_FREQUENCY
        
        self.slow_period_slider = Slider(
            x=10, y=150, width=150, height=10,
            min_val=5.0, max_val=60.0,
            initial_val=WAVE_SLOW_PERIOD,
            label="Slow Wave Period (s)"
        )
        self.wave_slow_period = WAVE_SLOW_PERIOD
        
        self.fast_amp_slider = Slider(
            x=10, y=200, width=150, height=10,
            min_val=10, max_val=100,
            initial_val=WAVE_FAST_AMPLITUDE,
            label="Fast Wave Amplitude"
        )
        self.wave_fast_amplitude = WAVE_FAST_AMPLITUDE
        
        self.slow_amp_slider = Slider(
            x=10, y=250, width=150, height=10,
            min_val=20, max_val=200,
            initial_val=WAVE_SLOW_AMPLITUDE,
            label="Slow Wave Amplitude"
        )
        self.wave_slow_amplitude = WAVE_SLOW_AMPLITUDE
    
    def generate_sand_surface(self):
        """Generate bumpy sand surface points"""
        self.sand_points = []
        
        for i in range(SAND_BUMP_COUNT + 1):
            t = i / SAND_BUMP_COUNT
            x = t * WINDOW_WIDTH
            
            # Base height (linear interpolation)
            base_y = SAND_LEFT_Y + t * (SAND_RIGHT_Y - SAND_LEFT_Y)
            
            # Add random bump (except at edges for clean connection)
            if i == 0 or i == SAND_BUMP_COUNT:
                bump = 0
            else:
                bump = random.uniform(-SAND_BUMP_HEIGHT, SAND_BUMP_HEIGHT)
            
            self.sand_points.append((x, base_y + bump))
    
    def create_boundaries(self):
        """Create static boundary shapes (walls only - sand is now particles)"""
        # Generate bumpy sand surface (used for initial sand particle placement)
        self.generate_sand_surface()
        
        # Add collision for the solid sand wedge (below the particle layers)
        base_offset = SAND_LAYERS * SAND_PARTICLE_SPACING
        wedge_top = pymunk.Segment(
            self.space.static_body,
            (0, SAND_LEFT_Y + base_offset),
            (WINDOW_WIDTH, SAND_RIGHT_Y + base_offset),
            3
        )
        wedge_top.friction = 0.8
        wedge_top.elasticity = 0.1
        wedge_top.collision_type = COLLISION_BOUNDARY
        wedge_top.filter = pymunk.ShapeFilter(categories=CAT_BOUNDARY, mask=MASK_BOUNDARY)
        self.space.add(wedge_top)
        
        # Add a solid floor beneath the sand
        floor = pymunk.Segment(
            self.space.static_body,
            (0, WINDOW_HEIGHT + 20),
            (WINDOW_WIDTH, WINDOW_HEIGHT + 20),
            20
        )
        floor.friction = 0.8
        floor.elasticity = 0.1
        floor.collision_type = COLLISION_BOUNDARY
        floor.filter = pymunk.ShapeFilter(categories=CAT_BOUNDARY, mask=MASK_BOUNDARY)
        self.space.add(floor)
        
        # Left wall
        left_wall = pymunk.Segment(
            self.space.static_body,
            (-10, 0), (-10, WINDOW_HEIGHT),
            10
        )
        left_wall.friction = 0.5
        left_wall.elasticity = 0.1
        left_wall.collision_type = COLLISION_BOUNDARY
        left_wall.filter = pymunk.ShapeFilter(categories=CAT_BOUNDARY, mask=MASK_BOUNDARY)
        self.space.add(left_wall)
        
        # Note: Right wall is now the wave generator (kinematic body)
        
        # Top boundary (to prevent particles escaping)
        top_wall = pymunk.Segment(
            self.space.static_body,
            (0, -10), (WINDOW_WIDTH, -10),
            10
        )
        top_wall.friction = 0.5
        top_wall.elasticity = 0.1
        top_wall.filter = pymunk.ShapeFilter(categories=CAT_BOUNDARY, mask=MASK_BOUNDARY)
        self.space.add(top_wall)
    
    def get_sand_height_at(self, x):
        """Get sand surface y coordinate at given x (interpolated from bumpy surface)"""
        # Clamp x to valid range
        x = max(0, min(WINDOW_WIDTH, x))
        
        # Find which segment we're in
        for i in range(len(self.sand_points) - 1):
            x1, y1 = self.sand_points[i]
            x2, y2 = self.sand_points[i + 1]
            
            if x1 <= x <= x2:
                # Linear interpolation within segment
                if x2 == x1:
                    return y1
                t = (x - x1) / (x2 - x1)
                return y1 + t * (y2 - y1)
        
        # Fallback to last point
        return self.sand_points[-1][1]
    
    def create_sand_particles(self):
        """Create sand particles along and below the bumpy surface"""
        self.sand_bodies = []
        self.sand_shapes = []
        
        spacing = SAND_PARTICLE_SPACING
        
        # Create sand particles in layers below the surface
        x = SAND_PARTICLE_RADIUS
        while x < WINDOW_WIDTH - SAND_PARTICLE_RADIUS:
            surface_y = self.get_sand_height_at(x)
            
            # Create multiple layers of sand below surface
            for layer in range(SAND_LAYERS):
                y = surface_y + layer * spacing
                
                # Don't create sand below screen
                if y > WINDOW_HEIGHT - SAND_PARTICLE_RADIUS:
                    continue
                
                # Add some randomness
                px = x + random.uniform(-1, 1)
                py = y + random.uniform(-1, 1)
                
                self.create_single_sand_particle(px, py)
            
            x += spacing
        
        print(f"Created {len(self.sand_bodies)} sand particles")
    
    def create_single_sand_particle(self, x, y):
        """Create a single sand particle at the given position"""
        body = pymunk.Body(SAND_PARTICLE_MASS, 
                          pymunk.moment_for_circle(SAND_PARTICLE_MASS, 0, SAND_PARTICLE_RADIUS))
        body.position = (x, y)
        
        shape = pymunk.Circle(body, SAND_PARTICLE_RADIUS)
        shape.friction = SAND_PARTICLE_FRICTION
        shape.elasticity = SAND_PARTICLE_ELASTICITY
        shape.collision_type = COLLISION_SAND
        shape.filter = pymunk.ShapeFilter(categories=CAT_SAND, mask=MASK_SAND)
        
        self.space.add(body, shape)
        self.sand_bodies.append(body)
        self.sand_shapes.append(shape)
        
        return body, shape
    
    def setup_collision_handlers(self):
        """Set up collision handling - we'll do erosion in update loop instead"""
        # Collision handlers are complex in pymunk, so we handle water-sand
        # interaction in the update loop by checking distances
        pass
    
    def process_erosion_deposition(self):
        """Process water-sand interactions for erosion and deposition"""
        contact_distance = PARTICLE_RADIUS + SAND_PARTICLE_RADIUS + 2
        
        sand_to_remove = []
        deposits = []
        
        for water_body in self.water_bodies:
            wx, wy = water_body.position
            sandiness = self.water_sandiness.get(water_body, 0)
            
            # Check for nearby sand particles
            for i, sand_body in enumerate(self.sand_bodies):
                if i in sand_to_remove:
                    continue
                    
                sx, sy = sand_body.position
                dist = math.sqrt((wx - sx)**2 + (wy - sy)**2)
                
                if dist < contact_distance:
                    # Calculate pickup probability (inversely proportional to sandiness)
                    pickup_prob = PICKUP_PROB_MAX - (sandiness / SANDINESS_MAX) * (PICKUP_PROB_MAX - PICKUP_PROB_MIN)
                    
                    # Calculate deposit probability (proportional to sandiness)
                    deposit_prob = DEPOSIT_PROB_MIN + (sandiness / SANDINESS_MAX) * (DEPOSIT_PROB_MAX - DEPOSIT_PROB_MIN)
                    
                    # Try to pick up sand
                    if sandiness < SANDINESS_MAX and random.random() < pickup_prob:
                        sand_to_remove.append(i)
                        self.water_sandiness[water_body] = sandiness + 1
                        sandiness += 1
                        break  # Only pick up one sand per frame
                    
                    # Try to deposit sand
                    elif sandiness > SANDINESS_MIN and random.random() < deposit_prob:
                        deposits.append((wx + random.uniform(-3, 3), wy + random.uniform(0, 5)))
                        self.water_sandiness[water_body] = sandiness - 1
                        sandiness -= 1
                        break  # Only deposit one sand per frame
        
        # Remove picked up sand (in reverse order)
        for i in sorted(sand_to_remove, reverse=True):
            body = self.sand_bodies[i]
            shape = self.sand_shapes[i]
            self.space.remove(body, shape)
            del self.sand_bodies[i]
            del self.sand_shapes[i]
        
        # Create deposited sand
        for x, y in deposits:
            self.create_single_sand_particle(x, y)
    
    def create_wave_generator(self):
        """Create the oscillating wave generator wall"""
        # Kinematic body - we control its position directly
        self.wave_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.wave_body.position = (WAVE_WALL_BASE_X, WINDOW_HEIGHT / 2)
        
        # Vertical wall segment - thick to prevent tunneling
        self.wave_shape = pymunk.Segment(
            self.wave_body,
            (0, -WINDOW_HEIGHT),  # Top of wall (relative to body)
            (0, WINDOW_HEIGHT),   # Bottom of wall (relative to body)
            WAVE_WALL_THICKNESS
        )
        self.wave_shape.friction = 0.3
        self.wave_shape.elasticity = 0.2
        self.wave_shape.collision_type = COLLISION_WAVE_WALL
        self.wave_shape.filter = pymunk.ShapeFilter(categories=CAT_WAVE_WALL, mask=MASK_WAVE_WALL)
        
        self.space.add(self.wave_body, self.wave_shape)
        
        # Add a static backup wall at the far right edge
        # This catches any particles that might slip through
        backup_wall = pymunk.Segment(
            self.space.static_body,
            (WINDOW_WIDTH + 10, 0),
            (WINDOW_WIDTH + 10, WINDOW_HEIGHT),
            10
        )
        backup_wall.friction = 0.5
        backup_wall.elasticity = 0.1
        backup_wall.collision_type = COLLISION_WAVE_WALL
        backup_wall.filter = pymunk.ShapeFilter(categories=CAT_WAVE_WALL, mask=MASK_WAVE_WALL)
        self.space.add(backup_wall)
    
    def update_wave_generator(self):
        """Update wave generator position based on combined sinusoidal motion"""
        # Fast wave (primary oscillation)
        fast_freq = self.wave_fast_frequency
        fast_amp = self.wave_fast_amplitude
        fast_offset = fast_amp * math.sin(2 * math.pi * fast_freq * self.time)
        fast_velocity = fast_amp * 2 * math.pi * fast_freq * math.cos(2 * math.pi * fast_freq * self.time)
        
        # Slow wave (secondary oscillation - creates longer swells)
        slow_freq = 1.0 / self.wave_slow_period  # Convert period to frequency
        slow_amp = self.wave_slow_amplitude
        slow_offset = slow_amp * math.sin(2 * math.pi * slow_freq * self.time)
        slow_velocity = slow_amp * 2 * math.pi * slow_freq * math.cos(2 * math.pi * slow_freq * self.time)
        
        # Combine both waves
        total_offset = fast_offset + slow_offset
        total_velocity = fast_velocity + slow_velocity
        
        new_x = WAVE_WALL_BASE_X + total_offset
        
        # Update body position and velocity
        self.wave_body.position = (new_x, self.wave_body.position.y)
        self.wave_body.velocity = (total_velocity, 0)
    
    def create_water_particles(self):
        """Create water particles as small circles"""
        self.water_bodies = []
        self.water_shapes = []
        
        spacing = PARTICLE_RADIUS * 2.8  # Tighter spacing for more water
        
        # Don't spawn particles past the wave wall's leftmost position
        # Account for both wave amplitudes when determining spawn area
        total_amplitude = WAVE_FAST_AMPLITUDE + WAVE_SLOW_AMPLITUDE
        max_x = WAVE_WALL_BASE_X - total_amplitude - WAVE_WALL_THICKNESS - PARTICLE_RADIUS * 2
        
        x = PARTICLE_RADIUS * 2
        while x < max_x:
            sand_y = self.get_sand_height_at(x)
            
            # Fill from water fill top down to just above sand
            y = WATER_FILL_TOP
            while y < sand_y - PARTICLE_RADIUS * 2:
                # Add some randomness
                px = x + random.uniform(-1, 1)
                py = y + random.uniform(-1, 1)
                
                # Create particle
                body = pymunk.Body(PARTICLE_MASS, pymunk.moment_for_circle(PARTICLE_MASS, 0, PARTICLE_RADIUS))
                body.position = (px, py)
                
                shape = pymunk.Circle(body, PARTICLE_RADIUS)
                shape.friction = PARTICLE_FRICTION
                shape.elasticity = PARTICLE_ELASTICITY
                shape.collision_type = COLLISION_WATER
                shape.filter = pymunk.ShapeFilter(categories=CAT_WATER, mask=MASK_WATER)
                
                self.space.add(body, shape)
                self.water_bodies.append(body)
                self.water_shapes.append(shape)
                
                # Initialize sandiness
                self.water_sandiness[body] = 0
                
                y += spacing
            
            x += spacing
        
        print(f"Created {len(self.water_bodies)} water particles")
    
    def update(self, dt):
        """Update simulation"""
        self.time += dt
        
        # Update wave generator position (sinusoidal motion)
        self.update_wave_generator()
        
        # Apply sand gravity (normal to average slope) to sand particles
        sand_gx = self.sand_gravity_dir[0] * GRAVITY
        sand_gy = self.sand_gravity_dir[1] * GRAVITY
        for body in self.sand_bodies:
            # Override gravity for sand particles
            body.velocity = (
                body.velocity.x + sand_gx * dt - self.space.gravity[0] * dt,
                body.velocity.y + sand_gy * dt - self.space.gravity[1] * dt + GRAVITY * dt
            )
        
        # Step physics simulation
        # Use fixed timestep for stability
        step_dt = 1/60
        steps = max(1, int(dt / step_dt))
        for _ in range(steps):
            self.space.step(step_dt)
        
        # Process erosion and deposition
        self.process_erosion_deposition()
            
        # Safety check: push any particles that got past the wave wall back
        wall_x = self.wave_body.position.x + WAVE_WALL_THICKNESS
        for body in self.water_bodies:
            if body.position.x > wall_x:
                body.position = (wall_x - PARTICLE_RADIUS - 1, body.position.y)
                body.velocity = (min(0, body.velocity.x), body.velocity.y)
    
    def draw_sand(self):
        """Draw solid sand base wedge and sand particles"""
        # First draw solid sand wedge underneath the particles
        # This creates the base layer below the dynamic sand particles
        base_offset = SAND_LAYERS * SAND_PARTICLE_SPACING  # How deep the particles go
        sand_base_points = [
            (0, SAND_LEFT_Y + base_offset),
            (WINDOW_WIDTH, SAND_RIGHT_Y + base_offset),
            (WINDOW_WIDTH, WINDOW_HEIGHT),
            (0, WINDOW_HEIGHT),
        ]
        pygame.draw.polygon(self.screen, SAND_COLOR, sand_base_points)
        
        # Draw sand particles on top
        for body in self.sand_bodies:
            x, y = int(body.position.x), int(body.position.y)
            if 0 <= x < WINDOW_WIDTH and 0 <= y < WINDOW_HEIGHT:
                pygame.draw.circle(self.screen, SAND_COLOR, (x, y), int(SAND_PARTICLE_RADIUS))
    
    def draw_particles(self):
        """Draw water particles"""
        for body in self.water_bodies:
            x, y = int(body.position.x), int(body.position.y)
            if 0 <= x < WINDOW_WIDTH and 0 <= y < WINDOW_HEIGHT:
                pygame.draw.circle(self.screen, WATER_COLOR, (x, y), PARTICLE_RADIUS)
    
    def draw_wave_generator(self):
        """Draw the wave generator wall"""
        x = int(self.wave_body.position.x)
        # Draw a thick vertical line for the wave wall
        pygame.draw.line(
            self.screen,
            (100, 100, 150),  # Grayish blue color
            (x, 0),
            (x, WINDOW_HEIGHT),
            WAVE_WALL_THICKNESS * 2
        )
    
    def draw_ui(self):
        """Draw UI elements"""
        font = pygame.font.Font(None, 24)
        
        text = font.render(f"Water: {len(self.water_bodies)} | Sand: {len(self.sand_bodies)}", True, (0, 0, 0))
        self.screen.blit(text, (10, 10))
        
        fps = self.clock.get_fps()
        text = font.render(f"FPS: {fps:.1f}", True, (0, 0, 0))
        self.screen.blit(text, (10, 30))
        
        text = font.render("R: reset", True, (0, 0, 0))
        self.screen.blit(text, (10, 50))
    
    def draw(self):
        """Render everything"""
        self.screen.fill(SKY_COLOR)
        self.draw_wave_generator()
        self.draw_sand()
        self.draw_particles()
        self.draw_ui()
        self.fast_freq_slider.draw(self.screen)
        self.slow_period_slider.draw(self.screen)
        self.fast_amp_slider.draw(self.screen)
        self.slow_amp_slider.draw(self.screen)
        pygame.display.flip()
    
    def reset(self):
        """Reset simulation"""
        # Remove all water particles
        for body, shape in zip(self.water_bodies, self.water_shapes):
            self.space.remove(body, shape)
        
        self.water_bodies.clear()
        self.water_shapes.clear()
        self.water_sandiness.clear()
        
        # Remove all sand particles
        for body, shape in zip(self.sand_bodies, self.sand_shapes):
            self.space.remove(body, shape)
        
        self.sand_bodies.clear()
        self.sand_shapes.clear()
        
        # Regenerate sand surface and recreate particles
        self.generate_sand_surface()
        self.create_sand_particles()
        self.create_water_particles()
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            # Let sliders handle events first
            if self.fast_freq_slider.handle_event(event):
                self.wave_fast_frequency = self.fast_freq_slider.value
            if self.slow_period_slider.handle_event(event):
                self.wave_slow_period = self.slow_period_slider.value
            if self.fast_amp_slider.handle_event(event):
                self.wave_fast_amplitude = self.fast_amp_slider.value
            if self.slow_amp_slider.handle_event(event):
                self.wave_slow_amplitude = self.slow_amp_slider.value
            
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.reset()
    
    def run(self):
        """Main loop"""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 1/30)
            
            self.handle_events()
            self.update(dt)
            self.draw()
        
        pygame.quit()


if __name__ == "__main__":
    simulator = BeachSimulator()
    simulator.run()

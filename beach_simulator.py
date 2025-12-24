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

# Water fill area
WATER_FILL_TOP = WINDOW_HEIGHT * 0.45

# Wave generator parameters (oscillating wall)
WAVE_WALL_BASE_X = WINDOW_WIDTH - 40  # Base position of wave wall
WAVE_WALL_AMPLITUDE = 40  # How far the wall moves left/right (reduced)
WAVE_WALL_FREQUENCY = 0.25  # Oscillations per second (Hz) - slower
WAVE_WALL_THICKNESS = 20  # Much thicker to prevent tunneling

# Collision types
COLLISION_WATER = 1
COLLISION_BOUNDARY = 2


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
        
        # Reduce collision iterations for performance
        self.space.iterations = 10
        
        # Create boundaries and particles
        self.create_boundaries()
        self.create_wave_generator()
        self.create_water_particles()
        
        # Debug draw options (optional)
        self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)
        
        # UI controls
        self.frequency_slider = Slider(
            x=10, y=100, width=150, height=10,
            min_val=0.05, max_val=1.0,
            initial_val=WAVE_WALL_FREQUENCY,
            label="Wave Speed"
        )
        self.wave_frequency = WAVE_WALL_FREQUENCY
    
    def create_boundaries(self):
        """Create static boundary shapes (sand slope and walls)"""
        # Sand slope - create as a polygon
        # Points: top-left of slope, top-right of slope, bottom-right, bottom-left
        sand_vertices = [
            (0, SAND_LEFT_Y),
            (WINDOW_WIDTH, SAND_RIGHT_Y),
            (WINDOW_WIDTH, WINDOW_HEIGHT + 50),
            (0, WINDOW_HEIGHT + 50),
        ]
        
        # Create static body for sand
        sand_body = pymunk.Body(body_type=pymunk.Body.STATIC)
        sand_shape = pymunk.Poly(sand_body, sand_vertices)
        sand_shape.friction = 0.8
        sand_shape.elasticity = 0.1
        sand_shape.collision_type = COLLISION_BOUNDARY
        self.space.add(sand_body, sand_shape)
        
        # Left wall
        left_wall = pymunk.Segment(
            self.space.static_body,
            (-10, 0), (-10, WINDOW_HEIGHT),
            10
        )
        left_wall.friction = 0.5
        left_wall.elasticity = 0.1
        left_wall.collision_type = COLLISION_BOUNDARY
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
        self.space.add(top_wall)
    
    def get_sand_height_at(self, x):
        """Get sand surface y coordinate at given x"""
        t = x / WINDOW_WIDTH
        return SAND_LEFT_Y + t * (SAND_RIGHT_Y - SAND_LEFT_Y)
    
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
        self.wave_shape.collision_type = COLLISION_BOUNDARY
        
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
        backup_wall.collision_type = COLLISION_BOUNDARY
        self.space.add(backup_wall)
    
    def update_wave_generator(self):
        """Update wave generator position based on sinusoidal motion"""
        # Use slider value for frequency
        freq = self.wave_frequency
        
        # Calculate new x position using sine wave
        # sin goes from -1 to 1, so position oscillates around base
        offset = WAVE_WALL_AMPLITUDE * math.sin(2 * math.pi * freq * self.time)
        new_x = WAVE_WALL_BASE_X + offset
        
        # Calculate velocity for smooth physics interaction
        # Derivative of sin is cos
        velocity = WAVE_WALL_AMPLITUDE * 2 * math.pi * freq * math.cos(2 * math.pi * freq * self.time)
        
        # Update body position and velocity
        self.wave_body.position = (new_x, self.wave_body.position.y)
        self.wave_body.velocity = (velocity, 0)
    
    def create_water_particles(self):
        """Create water particles as small circles"""
        self.water_bodies = []
        self.water_shapes = []
        
        spacing = PARTICLE_RADIUS * 3.5  # Wider spacing for better performance
        
        # Don't spawn particles past the wave wall's leftmost position
        max_x = WAVE_WALL_BASE_X - WAVE_WALL_AMPLITUDE - WAVE_WALL_THICKNESS - PARTICLE_RADIUS * 2
        
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
                
                self.space.add(body, shape)
                self.water_bodies.append(body)
                self.water_shapes.append(shape)
                
                y += spacing
            
            x += spacing
        
        print(f"Created {len(self.water_bodies)} water particles")
    
    def update(self, dt):
        """Update simulation"""
        self.time += dt
        
        # Update wave generator position (sinusoidal motion)
        self.update_wave_generator()
        
        # Step physics simulation
        # Use fixed timestep for stability
        step_dt = 1/60
        steps = max(1, int(dt / step_dt))
        for _ in range(steps):
            self.space.step(step_dt)
            
        # Safety check: push any particles that got past the wave wall back
        wall_x = self.wave_body.position.x + WAVE_WALL_THICKNESS
        for body in self.water_bodies:
            if body.position.x > wall_x:
                body.position = (wall_x - PARTICLE_RADIUS - 1, body.position.y)
                body.velocity = (min(0, body.velocity.x), body.velocity.y)
    
    def draw_sand(self):
        """Draw the sand slope"""
        points = [
            (0, SAND_LEFT_Y),
            (WINDOW_WIDTH, SAND_RIGHT_Y),
            (WINDOW_WIDTH, WINDOW_HEIGHT),
            (0, WINDOW_HEIGHT),
        ]
        pygame.draw.polygon(self.screen, SAND_COLOR, points)
        pygame.draw.line(self.screen, (200, 180, 150),
                        (0, SAND_LEFT_Y), (WINDOW_WIDTH, SAND_RIGHT_Y), 3)
    
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
        
        text = font.render(f"Particles: {len(self.water_bodies)}", True, (0, 0, 0))
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
        self.frequency_slider.draw(self.screen)
        pygame.display.flip()
    
    def reset(self):
        """Reset simulation"""
        # Remove all water particles
        for body, shape in zip(self.water_bodies, self.water_shapes):
            self.space.remove(body, shape)
        
        self.water_bodies.clear()
        self.water_shapes.clear()
        
        # Recreate particles
        self.create_water_particles()
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            # Let slider handle events first
            if self.frequency_slider.handle_event(event):
                self.wave_frequency = self.frequency_slider.value
            
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

"""
Beach Simulator using Pymunk for 2D physics with bitmap-based sand
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

# Sand bitmap resolution (pixels per cell)
SAND_CELL_SIZE = 4

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
SAND_BUMP_COUNT = 12  # Number of bump control points (fewer = smoother)
SAND_BUMP_HEIGHT = 20  # Maximum random bump height (pixels)

# Water fill area
WATER_FILL_TOP = WINDOW_HEIGHT * 0.35

# Wave generator parameters (oscillating wall)
WAVE_WALL_THICKNESS = 20

# Fast wave (primary oscillation)
WAVE_FAST_AMPLITUDE = 40
WAVE_FAST_FREQUENCY = 0.25

# Slow wave (secondary oscillation)
WAVE_SLOW_AMPLITUDE = 120
WAVE_SLOW_PERIOD = 10.0

# Base position
WAVE_WALL_BASE_X = WINDOW_WIDTH - 40 - WAVE_SLOW_AMPLITUDE

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

# Collision masks
MASK_WATER = CAT_WATER | CAT_SAND | CAT_BOUNDARY | CAT_WAVE_WALL
MASK_SAND = CAT_WATER | CAT_SAND | CAT_BOUNDARY
MASK_BOUNDARY = CAT_WATER | CAT_SAND | CAT_BOUNDARY | CAT_WAVE_WALL
MASK_WAVE_WALL = CAT_WATER

# Erosion/deposition parameters
SANDINESS_MIN = 0
SANDINESS_MAX = 10
PICKUP_PROB_MIN = 0.01   # 1% per frame at high sandiness
PICKUP_PROB_MAX = 0.02   # 2% per frame at low sandiness
DEPOSIT_PROB_MIN = 0.01  # 1% per frame at low sandiness
DEPOSIT_PROB_MAX = 0.02  # 2% per frame at high sandiness


class Slider:
    """Simple UI slider control"""
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.dragging = False
        
        self.bg_color = (100, 100, 100)
        self.fg_color = (150, 150, 200)
        self.handle_color = (200, 200, 220)
        self.text_color = (0, 0, 0)
        
        self.handle_rect = self._get_handle_rect()
    
    def _get_handle_rect(self):
        t = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.rect.x + int(t * self.rect.width) - 5
        return pygame.Rect(handle_x, self.rect.y - 3, 10, self.rect.height + 6)
    
    def _value_from_x(self, x):
        t = (x - self.rect.x) / self.rect.width
        t = max(0, min(1, t))
        return self.min_val + t * (self.max_val - self.min_val)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos) or self.rect.collidepoint(event.pos):
                self.dragging = True
                self.value = self._value_from_x(event.pos[0])
                self.handle_rect = self._get_handle_rect()
                return True
        
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.value = self._value_from_x(event.pos[0])
                self.handle_rect = self._get_handle_rect()
                return True
        
        return False
    
    def draw(self, screen):
        font = pygame.font.Font(None, 20)
        label_text = font.render(f"{self.label}: {self.value:.2f}", True, self.text_color)
        screen.blit(label_text, (self.rect.x, self.rect.y - 18))
        pygame.draw.rect(screen, self.bg_color, self.rect, border_radius=3)
        t = (self.value - self.min_val) / (self.max_val - self.min_val)
        filled_width = int(t * self.rect.width)
        filled_rect = pygame.Rect(self.rect.x, self.rect.y, filled_width, self.rect.height)
        pygame.draw.rect(screen, self.fg_color, filled_rect, border_radius=3)
        pygame.draw.rect(screen, self.handle_color, self.handle_rect, border_radius=2)


class BeachSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Beach Simulator - Bitmap Sand")
        self.clock = pygame.time.Clock()
        self.running = True
        self.time = 0.0
        self.last_frame_time = 0.0
        
        # Create pymunk space
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)
        self.space.iterations = 10
        
        # Sand bitmap dimensions
        self.sand_cols = WINDOW_WIDTH // SAND_CELL_SIZE
        self.sand_rows = WINDOW_HEIGHT // SAND_CELL_SIZE
        
        # Water particle tracking
        self.water_bodies = []
        self.water_shapes = []
        self.water_sandiness = {}
        
        # Sand collision shapes (will be updated when sand changes)
        self.sand_collision_shapes = []
        
        # Track which sand cells need stability check (optimization)
        self.dirty_sand_cells = set()
        
        # Initialize sand bitmap and create everything
        self.initialize_sand_bitmap()
        self.create_boundaries()
        self.create_sand_collision()
        self.create_wave_generator()
        self.create_water_particles()
        
        # Pre-render sand surface for performance
        self.sand_surface = None
        self.sand_dirty = True
        
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
    
    def initialize_sand_bitmap(self):
        """Initialize the sand bitmap with a sloped beach"""
        self.sand_bitmap = [[False] * self.sand_cols for _ in range(self.sand_rows)]
        
        # Generate bump control points
        control_points = []
        for i in range(SAND_BUMP_COUNT + 1):
            t = i / SAND_BUMP_COUNT
            base_y = SAND_LEFT_Y + t * (SAND_RIGHT_Y - SAND_LEFT_Y)
            
            # Add random bumps (except at edges)
            if 0 < i < SAND_BUMP_COUNT:
                bump = random.uniform(-SAND_BUMP_HEIGHT, SAND_BUMP_HEIGHT)
            else:
                bump = 0
            
            control_points.append(base_y + bump)
        
        # Interpolate smoothly between control points for each column
        self.surface_heights = []
        for col in range(self.sand_cols):
            t = col / (self.sand_cols - 1) if self.sand_cols > 1 else 0
            
            # Find which control point segment we're in
            segment_t = t * SAND_BUMP_COUNT
            i = int(segment_t)
            i = min(i, SAND_BUMP_COUNT - 1)  # Clamp to valid range
            
            # Local t within segment (0 to 1)
            local_t = segment_t - i
            
            # Smooth interpolation (smoothstep)
            smooth_t = local_t * local_t * (3 - 2 * local_t)
            
            # Interpolate between control points
            y = control_points[i] + smooth_t * (control_points[i + 1] - control_points[i])
            self.surface_heights.append(y)
        
        # Fill bitmap below the surface
        for col in range(self.sand_cols):
            surface_row = int(self.surface_heights[col] / SAND_CELL_SIZE)
            for row in range(surface_row, self.sand_rows):
                self.sand_bitmap[row][col] = True
    
    def get_sand_surface_y(self, x):
        """Get the sand surface Y at a given X coordinate"""
        col = int(x / SAND_CELL_SIZE)
        col = max(0, min(col, self.sand_cols - 1))
        return self.surface_heights[col]
    
    def is_sand_edge(self, row, col):
        """Check if a sand cell is on the edge (adjacent to empty space)"""
        if not self.sand_bitmap[row][col]:
            return False
        
        # Check 4-neighbors
        neighbors = [
            (row - 1, col), (row + 1, col),
            (row, col - 1), (row, col + 1)
        ]
        
        for nr, nc in neighbors:
            if 0 <= nr < self.sand_rows and 0 <= nc < self.sand_cols:
                if not self.sand_bitmap[nr][nc]:
                    return True
            elif nr < 0:  # Above the bitmap = empty
                return True
        
        return False
    
    def is_adjacent_to_sand(self, row, col):
        """Check if an empty cell is adjacent to sand"""
        if row < 0 or row >= self.sand_rows or col < 0 or col >= self.sand_cols:
            return False
        if self.sand_bitmap[row][col]:
            return False  # Already sand
        
        # Check 4-neighbors
        neighbors = [
            (row - 1, col), (row + 1, col),
            (row, col - 1), (row, col + 1)
        ]
        
        for nr, nc in neighbors:
            if 0 <= nr < self.sand_rows and 0 <= nc < self.sand_cols:
                if self.sand_bitmap[nr][nc]:
                    return True
        
        return False
    
    def create_boundaries(self):
        """Create static boundary shapes (walls only)"""
        # Floor
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
        
        # Top boundary
        top_wall = pymunk.Segment(
            self.space.static_body,
            (0, -10), (WINDOW_WIDTH, -10),
            10
        )
        top_wall.friction = 0.5
        top_wall.elasticity = 0.1
        top_wall.filter = pymunk.ShapeFilter(categories=CAT_BOUNDARY, mask=MASK_BOUNDARY)
        self.space.add(top_wall)
    
    def create_sand_collision(self):
        """Create collision shapes along the sand surface"""
        # Remove old collision shapes
        for shape in self.sand_collision_shapes:
            self.space.remove(shape)
        self.sand_collision_shapes.clear()
        
        # Find the surface of the sand bitmap
        surface_points = []
        for col in range(self.sand_cols):
            # Find topmost sand cell in this column
            for row in range(self.sand_rows):
                if self.sand_bitmap[row][col]:
                    x = col * SAND_CELL_SIZE
                    y = row * SAND_CELL_SIZE
                    surface_points.append((x, y))
                    break
            else:
                # No sand in this column
                x = col * SAND_CELL_SIZE
                y = WINDOW_HEIGHT
                surface_points.append((x, y))
        
        # Create segments along the surface with good thickness
        for i in range(len(surface_points) - 1):
            p1 = surface_points[i]
            p2 = surface_points[i + 1]
            
            segment = pymunk.Segment(
                self.space.static_body,
                p1, p2,
                SAND_CELL_SIZE  # Thicker segments to prevent tunneling
            )
            segment.friction = 0.8
            segment.elasticity = 0.1
            segment.collision_type = COLLISION_SAND
            segment.filter = pymunk.ShapeFilter(categories=CAT_SAND, mask=MASK_SAND)
            self.space.add(segment)
            self.sand_collision_shapes.append(segment)
        
        # Add vertical segments at steep height changes to block particles
        for i in range(len(surface_points) - 1):
            p1 = surface_points[i]
            p2 = surface_points[i + 1]
            
            height_diff = abs(p2[1] - p1[1])
            if height_diff > SAND_CELL_SIZE:
                # Add a vertical blocker
                if p2[1] > p1[1]:  # Slope goes down to the right
                    vert_segment = pymunk.Segment(
                        self.space.static_body,
                        (p2[0], p1[1]), (p2[0], p2[1]),
                        SAND_CELL_SIZE
                    )
                else:  # Slope goes up to the right
                    vert_segment = pymunk.Segment(
                        self.space.static_body,
                        (p1[0], p2[1]), (p1[0], p1[1]),
                        SAND_CELL_SIZE
                    )
                vert_segment.friction = 0.8
                vert_segment.elasticity = 0.1
                vert_segment.collision_type = COLLISION_SAND
                vert_segment.filter = pymunk.ShapeFilter(categories=CAT_SAND, mask=MASK_SAND)
                self.space.add(vert_segment)
                self.sand_collision_shapes.append(vert_segment)
    
    def create_wave_generator(self):
        """Create the oscillating wave generator wall"""
        self.wave_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.wave_body.position = (WAVE_WALL_BASE_X, WINDOW_HEIGHT / 2)
        
        self.wave_shape = pymunk.Segment(
            self.wave_body,
            (0, -WINDOW_HEIGHT),
            (0, WINDOW_HEIGHT),
            WAVE_WALL_THICKNESS
        )
        self.wave_shape.friction = 0.3
        self.wave_shape.elasticity = 0.2
        self.wave_shape.collision_type = COLLISION_WAVE_WALL
        self.wave_shape.filter = pymunk.ShapeFilter(categories=CAT_WAVE_WALL, mask=MASK_WAVE_WALL)
        
        self.space.add(self.wave_body, self.wave_shape)
        
        # Backup wall
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
        """Update wave generator position"""
        fast_freq = self.wave_fast_frequency
        fast_amp = self.wave_fast_amplitude
        fast_offset = fast_amp * math.sin(2 * math.pi * fast_freq * self.time)
        fast_velocity = fast_amp * 2 * math.pi * fast_freq * math.cos(2 * math.pi * fast_freq * self.time)
        
        slow_freq = 1.0 / self.wave_slow_period
        slow_amp = self.wave_slow_amplitude
        slow_offset = slow_amp * math.sin(2 * math.pi * slow_freq * self.time)
        slow_velocity = slow_amp * 2 * math.pi * slow_freq * math.cos(2 * math.pi * slow_freq * self.time)
        
        total_offset = fast_offset + slow_offset
        total_velocity = fast_velocity + slow_velocity
        
        new_x = WAVE_WALL_BASE_X + total_offset
        
        self.wave_body.position = (new_x, self.wave_body.position.y)
        self.wave_body.velocity = (total_velocity, 0)
    
    def create_water_particles(self):
        """Create water particles"""
        self.water_bodies = []
        self.water_shapes = []
        
        spacing = PARTICLE_RADIUS * 2.8
        
        total_amplitude = WAVE_FAST_AMPLITUDE + WAVE_SLOW_AMPLITUDE
        max_x = WAVE_WALL_BASE_X - total_amplitude - WAVE_WALL_THICKNESS - PARTICLE_RADIUS * 2
        
        x = PARTICLE_RADIUS * 2
        while x < max_x:
            sand_y = self.get_sand_surface_y(x)
            
            y = WATER_FILL_TOP
            while y < sand_y - PARTICLE_RADIUS * 2:
                px = x + random.uniform(-1, 1)
                py = y + random.uniform(-1, 1)
                
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
                
                self.water_sandiness[body] = 0
                
                y += spacing
            
            x += spacing
        
        print(f"Created {len(self.water_bodies)} water particles")
    
    def process_erosion_deposition(self):
        """Process water-sand interactions using the bitmap"""
        sand_changed = False
        
        for water_body in self.water_bodies:
            wx, wy = water_body.position
            sandiness = self.water_sandiness.get(water_body, 0)
            
            # Convert water position to bitmap cell
            col = int(wx / SAND_CELL_SIZE)
            row = int(wy / SAND_CELL_SIZE)
            
            # Check cells near the water particle
            check_radius = 2  # Check nearby cells
            did_action = False
            
            for dr in range(-check_radius, check_radius + 1):
                if did_action:
                    break
                for dc in range(-check_radius, check_radius + 1):
                    nr, nc = row + dr, col + dc
                    
                    if not (0 <= nr < self.sand_rows and 0 <= nc < self.sand_cols):
                        continue
                    
                    # Calculate probability based on sandiness
                    pickup_prob = PICKUP_PROB_MAX - (sandiness / SANDINESS_MAX) * (PICKUP_PROB_MAX - PICKUP_PROB_MIN)
                    deposit_prob = DEPOSIT_PROB_MIN + (sandiness / SANDINESS_MAX) * (DEPOSIT_PROB_MAX - DEPOSIT_PROB_MIN)
                    
                    # Try to pick up sand (must be on edge)
                    if self.sand_bitmap[nr][nc] and self.is_sand_edge(nr, nc):
                        if sandiness < SANDINESS_MAX and random.random() < pickup_prob:
                            self.sand_bitmap[nr][nc] = False
                            self.mark_neighbors_dirty(nr, nc)  # Trigger gravity check
                            self.water_sandiness[water_body] = sandiness + 1
                            sand_changed = True
                            did_action = True
                            break
                    
                    # Try to deposit sand (must be adjacent to existing sand)
                    elif not self.sand_bitmap[nr][nc] and self.is_adjacent_to_sand(nr, nc):
                        if sandiness > SANDINESS_MIN and random.random() < deposit_prob:
                            self.sand_bitmap[nr][nc] = True
                            self.mark_neighbors_dirty(nr, nc)  # Trigger gravity check
                            self.water_sandiness[water_body] = sandiness - 1
                            sand_changed = True
                            did_action = True
                            break
        
        # Update collision shapes if sand changed
        if sand_changed:
            self.create_sand_collision()
            self.sand_dirty = True
    
    def check_sand_stability(self, row, col):
        """Check if a sand pixel is stable, returns (stable, new_row, new_col)"""
        if not self.sand_bitmap[row][col]:
            return True, row, col  # No sand here, nothing to do
        
        if row >= self.sand_rows - 1:
            return True, row, col  # Bottom row is always stable
        
        def get_pixel(dr, dc):
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.sand_rows and 0 <= nc < self.sand_cols:
                return self.sand_bitmap[nr][nc]
            return True  # Out of bounds = solid
        
        p1 = get_pixel(1, -1)   # below-left
        p2 = get_pixel(1, 0)    # below
        p3 = get_pixel(1, 1)    # below-right
        p4 = get_pixel(0, -1)   # left
        p6 = get_pixel(0, 1)    # right
        p7 = get_pixel(-1, -1)  # above-left
        p9 = get_pixel(-1, 1)   # above-right
        
        # Check stability conditions
        if p2 and (p1 or p3):
            return True, row, col
        if p1 and p4 and p7:
            return True, row, col
        if p3 and p6 and p9:
            return True, row, col
        
        # Unstable - determine where to move
        if not p2:
            return False, row + 1, col  # Fall down
        else:
            return False, row + 1, col - 1  # Slide down-left
    
    def mark_neighbors_dirty(self, row, col):
        """Mark all 8 neighbors of a cell as needing stability check"""
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < self.sand_rows and 0 <= nc < self.sand_cols:
                    self.dirty_sand_cells.add((nr, nc))
    
    def process_sand_gravity(self):
        """Process sand gravity - only check dirty cells"""
        if not self.dirty_sand_cells:
            return
        
        sand_changed = False
        
        # Sort dirty cells by row (bottom to top) for proper processing
        cells_to_check = sorted(self.dirty_sand_cells, key=lambda x: -x[0])
        self.dirty_sand_cells.clear()
        
        for row, col in cells_to_check:
            if not self.sand_bitmap[row][col]:
                continue
            
            stable, new_row, new_col = self.check_sand_stability(row, col)
            
            if not stable:
                # Remove from old position
                self.sand_bitmap[row][col] = False
                self.mark_neighbors_dirty(row, col)
                
                # Add to new position if valid
                if 0 <= new_row < self.sand_rows and 0 <= new_col < self.sand_cols:
                    self.sand_bitmap[new_row][new_col] = True
                    self.mark_neighbors_dirty(new_row, new_col)
                
                sand_changed = True
        
        if sand_changed:
            self.create_sand_collision()
            self.sand_dirty = True
    
    def update(self, dt):
        """Update simulation"""
        self.time += dt
        
        self.update_wave_generator()
        
        # Step physics
        step_dt = 1/60
        steps = max(1, int(dt / step_dt))
        for _ in range(steps):
            self.space.step(step_dt)
        
        # Process erosion/deposition
        self.process_erosion_deposition()
        
        # Process sand gravity
        self.process_sand_gravity()
        
        # Safety check for wave wall
        wall_x = self.wave_body.position.x + WAVE_WALL_THICKNESS
        for body in self.water_bodies:
            if body.position.x > wall_x:
                body.position = (wall_x - PARTICLE_RADIUS - 1, body.position.y)
                body.velocity = (min(0, body.velocity.x), body.velocity.y)
        
        # Safety check: push water out of sand
        for body in self.water_bodies:
            wx, wy = body.position
            col = int(wx / SAND_CELL_SIZE)
            row = int(wy / SAND_CELL_SIZE)
            
            # Check if water is inside sand
            if 0 <= col < self.sand_cols and 0 <= row < self.sand_rows:
                if self.sand_bitmap[row][col]:
                    # Find the surface above this point
                    surface_row = row
                    while surface_row > 0 and self.sand_bitmap[surface_row - 1][col]:
                        surface_row -= 1
                    
                    # Push water to just above the sand surface
                    new_y = surface_row * SAND_CELL_SIZE - PARTICLE_RADIUS - 1
                    body.position = (wx, new_y)
                    # Dampen downward velocity
                    if body.velocity.y > 0:
                        body.velocity = (body.velocity.x, -body.velocity.y * 0.3)
    
    def render_sand_surface(self):
        """Render sand to a surface for performance"""
        self.sand_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        
        for row in range(self.sand_rows):
            for col in range(self.sand_cols):
                if self.sand_bitmap[row][col]:
                    x = col * SAND_CELL_SIZE
                    y = row * SAND_CELL_SIZE
                    pygame.draw.rect(
                        self.sand_surface,
                        SAND_COLOR,
                        (x, y, SAND_CELL_SIZE, SAND_CELL_SIZE)
                    )
        
        self.sand_dirty = False
    
    def draw_sand(self):
        """Draw sand from cached surface"""
        if self.sand_dirty or self.sand_surface is None:
            self.render_sand_surface()
        
        self.screen.blit(self.sand_surface, (0, 0))
    
    def draw_particles(self):
        """Draw water particles"""
        for body in self.water_bodies:
            x, y = int(body.position.x), int(body.position.y)
            if 0 <= x < WINDOW_WIDTH and 0 <= y < WINDOW_HEIGHT:
                pygame.draw.circle(self.screen, WATER_COLOR, (x, y), PARTICLE_RADIUS)
    
    def draw_wave_generator(self):
        """Draw the wave generator wall"""
        x = int(self.wave_body.position.x)
        pygame.draw.line(
            self.screen,
            (100, 100, 150),
            (x, 0),
            (x, WINDOW_HEIGHT),
            WAVE_WALL_THICKNESS * 2
        )
    
    def draw_ui(self):
        """Draw UI elements"""
        font = pygame.font.Font(None, 24)
        
        text = font.render(f"Water: {len(self.water_bodies)}", True, (0, 0, 0))
        self.screen.blit(text, (10, 10))
        
        fps = self.clock.get_fps()
        text = font.render(f"FPS: {fps:.1f}", True, (0, 0, 0))
        self.screen.blit(text, (10, 30))
        
        text = font.render("R: reset", True, (0, 0, 0))
        self.screen.blit(text, (10, 50))
        
        # Frame time (latency) in top right
        frame_time_ms = self.last_frame_time * 1000
        latency_text = font.render(f"{frame_time_ms:.1f} ms", True, (0, 0, 0))
        text_rect = latency_text.get_rect()
        self.screen.blit(latency_text, (WINDOW_WIDTH - text_rect.width - 10, 10))
    
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
        # Remove water particles
        for body, shape in zip(self.water_bodies, self.water_shapes):
            self.space.remove(body, shape)
        
        self.water_bodies.clear()
        self.water_shapes.clear()
        self.water_sandiness.clear()
        
        # Reinitialize sand bitmap
        self.initialize_sand_bitmap()
        self.create_sand_collision()
        self.sand_dirty = True
        self.dirty_sand_cells.clear()
        
        # Recreate water
        self.create_water_particles()
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
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
        import time
        while self.running:
            frame_start = time.perf_counter()
            
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 1/30)
            
            self.handle_events()
            self.update(dt)
            self.draw()
            
            self.last_frame_time = time.perf_counter() - frame_start
        
        pygame.quit()


if __name__ == "__main__":
    simulator = BeachSimulator()
    simulator.run()

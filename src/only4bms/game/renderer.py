import math
import time
import pygame
from pygame._sdl2.video import Texture
from .constants import (
    BASE_W, BASE_H, JUDGMENT_DEFS, HIT_ZONE_VISUAL_H, GREAT_ZONE_VISUAL_H,
    HIT_ZONE_PULSE_PERIOD, HIT_ZONE_ALPHA_MIN, HIT_ZONE_ALPHA_RANGE,
    LANE_BG_ALPHA, NUM_LANES, HIT_Y, NOTE_H, JUDGMENT_ORDER
)

class GameRenderer:
    def __init__(self, renderer, window_size):
        self.renderer = renderer
        self.width, self.height = window_size
        self.sx = self.width / BASE_W
        self.sy = self.height / BASE_H
        
        self.font = pygame.font.SysFont(None, self._s(48))
        self.bold_font = pygame.font.SysFont(None, self._s(56), bold=True)
        self.offscreen_hud = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.hud_texture = None
        
        self.bga_texture = None # Video frame or static image
        self.bga_updated_once = False
        
        # --- Cache for performance ---
        self.circle_note_cache = {} # (color, alpha, size) -> Texture
        self.bar_effect_cache = {}  # (color, alpha, r) -> Texture
        self.circle_effect_cache = {} # (color, alpha, r) -> Texture
        self.text_cache = {} # (text, font_id, color, alpha) -> Texture
        self.ai_vision_texture = None # Pre-rendered scanner static part
        
    def _s(self, v): return int(v * self.sy)
    def _sx(self, v): return int(v * self.sx)

    def _get_circle_note_texture(self, color, alpha, lane_w):
        key = (color, alpha, lane_w)
        if key not in self.circle_note_cache:
            cr = int(lane_w * 0.4)
            surf = pygame.Surface((lane_w, lane_w), pygame.SRCALPHA)
            # 1. Circular Shadow
            shadow_color = (0, 0, 0, int(160 * (alpha/255)))
            pygame.draw.circle(surf, shadow_color, (lane_w // 2, lane_w // 2 + 2), cr)
            # 2. Main Body
            pygame.draw.circle(surf, (*color, alpha), (lane_w // 2, lane_w // 2), cr)
            # 3. Top highlight
            pygame.draw.circle(surf, (255, 255, 255, int(160 * (alpha/255))), (lane_w // 2, lane_w // 2 - 1), cr - 1, 3)
            # 4. Inner small circle
            pygame.draw.circle(surf, (255, 255, 255, int(110 * (alpha/255))), (lane_w // 2, lane_w // 2), cr // 3, 2)
            self.circle_note_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.circle_note_cache[key]

    def _get_bar_effect_texture(self, color, alpha, r, lane_w):
        key = (color, alpha, r, lane_w)
        if key not in self.bar_effect_cache:
            bw = int(lane_w * 0.8) + r * 2
            bh = self._s(15 + r // 6)
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(surf, (*color, alpha), (0, 0, bw, bh), width=self._s(3), border_radius=self._s(4))
            core_w = int(lane_w * 0.8); core_h = max(1, bh // 3)
            pygame.draw.rect(surf, (255, 255, 255, min(255, alpha)), (r, (bh - core_h) // 2, core_w, core_h), border_radius=self._s(2))
            self.bar_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.bar_effect_cache[key]

    def _get_circle_effect_texture(self, color, alpha, r):
        key = (color, alpha, r)
        if key not in self.circle_effect_cache:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, alpha), (r, r), r, self._s(3))
            core_r = max(1, r // 2)
            pygame.draw.circle(surf, (255, 255, 255, min(255, alpha * 2)), (r, r), core_r)
            self.circle_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.circle_effect_cache[key]

    def _get_text_texture(self, text, is_bold, color, alpha, size_override=None):
        key = (text, is_bold, color, alpha, size_override)
        if key not in self.text_cache:
            if size_override:
                font = pygame.font.SysFont(None, size_override, bold=is_bold)
            else:
                font = self.bold_font if is_bold else self.font
            surf = font.render(text, True, (*color, alpha))
            self.text_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.text_cache[key]

    def _draw_ai_vision(self, x, y, w, h, alpha):
        if not self.ai_vision_texture or self.ai_vision_texture.width != w or self.ai_vision_texture.height != h:
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            v_color = (0, 255, 255, 255)
            # Scanner Frame (Dashed)
            dash = self._s(10); gap = self._s(6)
            for dx in range(0, w, dash + gap):
                dw = min(dash, w - dx)
                pygame.draw.line(surf, v_color, (dx, 0), (dx + dw, 0), 2)
                pygame.draw.line(surf, v_color, (dx, h - 2), (dx + dw, h - 2), 2)
            for dy in range(0, h, dash + gap):
                dh = min(dash, h - dy)
                pygame.draw.line(surf, v_color, (0, dy), (0, dy + dh), 2)
                pygame.draw.line(surf, v_color, (w - 2, dy), (w - 2, dy + dh), 2)
            
            # Robot Eyes
            er = self._s(8); ex = self._s(25); ey = h // 2
            pygame.draw.circle(surf, (255, 255, 255, 255), (w // 2 - ex, ey), er // 2)
            pygame.draw.circle(surf, (0, 255, 255, 180), (w // 2 - ex, ey), er, 2)
            pygame.draw.circle(surf, (255, 255, 255, 255), (w // 2 + ex, ey), er // 2)
            pygame.draw.circle(surf, (0, 255, 255, 180), (w // 2 + ex, ey), er, 2)
            
            # Text
            ai_font = pygame.font.SysFont(None, self._s(22), bold=True)
            ai_surf = ai_font.render("AI Vision", True, (0, 255, 255, 200))
            surf.blit(ai_surf, (self._s(8), self._s(5)))
            
            if self.ai_vision_texture: self.ai_vision_texture.update(surf)
            else: self.ai_vision_texture = Texture.from_surface(self.renderer, surf)

        # Glow
        self.renderer.draw_color = (0, 100, 150, alpha // 6)
        self.renderer.fill_rect((x, y, w, h))
        
        # Frame & Eyes (Blit the pre-rendered texture)
        self.ai_vision_texture.alpha = alpha
        self.renderer.blit(self.ai_vision_texture, pygame.Rect(x, y, w, h))

    def draw_playing(self, current_time, game_state):
        """
        game_state keys:
        - lane_x (list of x positions)
        - notes (list of notes)
        - lane_pressed (list of bool)
        - judgments (dict)
        - combo (int)
        - judgment_text (str)
        - judgment_color (tuple)
        - judgment_timer (int)
        - lane_total_w (int)
        - speed (float)
        - hw_mult (float)
        """
        lx = game_state['lane_x']
        notes = game_state['notes']
        pressed = game_state['lane_pressed']
        judgments = game_state['judgments']
        comb = game_state['combo']
        j_text = game_state['judgment_text']
        j_color = game_state['judgment_color']
        j_timer = game_state['judgment_timer']
        ltw = game_state['lane_total_w']
        spd = game_state['speed']
        hw = game_state['hw_mult']
        current_visual_time = game_state.get('current_visual_time', current_time)
        lane_w = lx[1] - lx[0] if len(lx) > 1 else self._sx(75)
        note_h = self._s(NOTE_H)
        hit_y = self._s(HIT_Y)

        self.offscreen_hud.fill((0, 0, 0, 0))
        
        # Judgment Pulse (Halved thickness for precision)
        perf_h = max(2, self._s(int(HIT_ZONE_VISUAL_H * hw // 2)))
        great_h = max(2, self._s(int(GREAT_ZONE_VISUAL_H * hw // 2)))
        pulse = (math.sin(current_time / HIT_ZONE_PULSE_PERIOD) + 1) / 2
        hit_alpha = int(HIT_ZONE_ALPHA_MIN + pulse * HIT_ZONE_ALPHA_RANGE)

        # Lane boundaries, BG, Hit Zone, and HUD text (Combo/Judgment)
        fade_mult = 1.0
        passed_time = game_state.get('all_notes_passed_time')
        if passed_time is not None:
            elapsed = current_time - passed_time
            fade_mult = max(0.0, 1.0 - elapsed / 500.0) # 500ms fade duration

        if fade_mult > 0:
            # Boundaries
            self.renderer.draw_color = (60, 60, 60, int(100 * fade_mult))
            self.renderer.draw_rect((lx[0] - 2, 0, ltw + 4, self.height))

            # Lane BG
            for i in range(NUM_LANES):
                bg_alpha = int(LANE_BG_ALPHA * fade_mult)
                self.renderer.draw_color = (30, 30, 30, bg_alpha) if not pressed[i] else (50, 50, 60, bg_alpha)
                self.renderer.fill_rect((lx[i], 0, lane_w, self.height))
                self.renderer.draw_color = (60, 60, 60, int(100 * fade_mult))
                self.renderer.draw_line((lx[i] + lane_w, 0), (lx[i] + lane_w, self.height))

            # Hit Zone
            self.renderer.draw_color = (0, 0, 0, int(150 * fade_mult))
            self.renderer.fill_rect((lx[0], hit_y, ltw, self.height - hit_y))
            # Judgment line sits ABOVE hit_y (bottom edge at hit_y)
            self.renderer.draw_color = (255, 40, 40, int(hit_alpha * fade_mult))
            self.renderer.fill_rect((lx[0], hit_y - perf_h, ltw, perf_h))
            self.renderer.draw_color = (255, 80, 80, int(min(255, hit_alpha + 150) * fade_mult))
            self.renderer.draw_rect((lx[0], hit_y - perf_h, ltw, perf_h))

            # AI Vision Area
            if game_state.get('is_ai'):
                vh = self._s(120)
                vy = hit_y - vh
                self._draw_ai_vision(lx[0], vy, ltw, vh, int(hit_alpha * 0.8 * fade_mult))

            # Judgment / Combo Text
            def get_bounce(timer, duration=200):
                elapsed = current_time - timer
                if elapsed < 0 or elapsed > duration: return 1.0
                t = elapsed / duration
                return 1.4 - 0.4 * (1 - (1 - t)**2)

            if j_text and current_time - j_timer < 500:
                dt = current_time - j_timer
                alpha = int(max(0, 255 * (1 - dt / 500)) * fade_mult)
                if alpha > 0:
                    tex = self._get_text_texture(j_text, False, j_color, alpha)
                    scale = get_bounce(j_timer)
                    tw, th = int(tex.width * scale), int(tex.height * scale)
                    self.renderer.blit(tex, pygame.Rect(lx[0] + ltw // 2 - tw // 2, self.height // 2 - self._s(50) - th // 2, tw, th))

            c_timer = game_state.get('combo_timer', 0)
            if comb > 0 and current_time - c_timer < 500:
                dt = current_time - c_timer
                alpha = int(max(0, 255 * (1 - dt / 500)) * fade_mult)
                if alpha > 0:
                    tex = self._get_text_texture(str(comb), True, (255, 255, 255), alpha)
                    scale = get_bounce(c_timer, 150)
                    tw, th = int(tex.width * scale), int(tex.height * scale)
                    self.renderer.blit(tex, pygame.Rect(lx[0] + ltw // 2 - tw // 2, self.height // 2 + self._s(20) - th // 2, tw, th))

        # Notes
        held_ln_ids = [id(n) for n in game_state.get('held_lns', []) if n is not None]
        for note in notes:
            is_hit = 'hit' in note
            is_miss = 'miss' in note
            is_held = id(note) in held_ln_ids
            
            # Draw if not missed AND (not hit OR is currently being held)
            if not is_miss and (not is_hit or is_held):
                # Use visual time for distance calculation (supports variable speed)
                td = note.get('visual_time_ms', note['time_ms']) - current_visual_time
                y = (hit_y - note_h) - td * spd
                
                # If held, pin the head to the hit line
                if is_held:
                    y = hit_y - note_h

                if -note_h <= y <= self.height:
                    note_type = game_state.get('note_type', 0) # 0: Bar, 1: Circle
                    color = (0, 255, 255)
                    is_auto = note.get('is_auto', False)
                    alpha = 60 if is_auto else 255
                    nx, ny = lx[note['lane']], int(y)
                    
                    # ── Long Note Body ──
                    if note.get('is_ln') and ('end_time_ms' in note or 'visual_end_time_ms' in note):
                        v_end_time = note.get('visual_end_time_ms', note.get('end_time_ms', note['time_ms']))
                        etd = v_end_time - current_visual_time
                        ey = (hit_y - note_h) - etd * spd
                        body_h = int(y - ey)
                        if body_h > 0:
                            b_alpha = int(alpha * 0.6)
                            self.renderer.draw_color = (*color, b_alpha)
                            # Body width matches the note head width (80% for both now)
                            body_margin = int(lane_w * 0.12) # Slightly narrower for better look
                            self.renderer.fill_rect((nx + body_margin, int(ey) + note_h // 2, lane_w - body_margin * 2, body_h + note_h // 2))
                            # Borders
                            self.renderer.draw_color = (*color, alpha)
                            self.renderer.draw_line((nx + body_margin, int(ey) + note_h // 2), (nx + body_margin, int(y) + note_h // 2))
                            self.renderer.draw_line((nx + lane_w - body_margin, int(ey) + note_h // 2), (nx + lane_w - body_margin, int(y) + note_h // 2))

                    # ── Note Head ──
                    if note_type == 0: # ── Bar View ──
                        # Thicker and narrower (80% width)
                        bw = int(lane_w * 0.8)
                        bh = int(note_h * 1.5)
                        bx = nx + (lane_w - bw) // 2
                        by = ny + (note_h - bh) # Align bottom edge with ny + note_h
                        
                        self.renderer.draw_color = (0, 0, 0, int(180 * (alpha/255)))
                        self.renderer.fill_rect((bx, by + bh - 4, bw, 4))
                        self.renderer.draw_color = (*color, alpha)
                        self.renderer.fill_rect((bx, by, bw, bh - 2))
                        # Top highlight
                        self.renderer.draw_color = (255, 255, 255, int(150 * (alpha/255)))
                        self.renderer.fill_rect((bx, by, bw, 2))
                        # CENTER LINE
                        self.renderer.draw_color = (255, 255, 255, int(110 * (alpha/255)))
                        self.renderer.draw_line((bx, by + bh // 2), (bx + bw, by + bh // 2))
                    else: # ── Circle View ──
                        tex = self._get_circle_note_texture(color, alpha, lane_w)
                        self.renderer.blit(tex, pygame.Rect(nx, ny + note_h // 2 - lane_w // 2, lane_w, lane_w))

    def draw_bga(self, current_time, bid, assets):
        tex = None
        if bid is not None:
            if bid in assets.videos:
                new_img = assets.videos[bid].get_frame(current_time)
                if new_img:
                    if not self.bga_texture:
                        self.bga_texture = Texture.from_surface(self.renderer, new_img)
                    else:
                        self.bga_texture.update(new_img)
                    self.bga_updated_once = True
                tex = self.bga_texture if self.bga_updated_once else assets.textures.get(bid)
            else:
                tex = assets.textures.get(bid)
            
        if not tex and assets.cover_texture:
            tex = assets.cover_texture
            
        if tex:
            tw, th = tex.width, tex.height
            scaled_h = int(th * self.width / tw)
            self.renderer.blit(tex, pygame.Rect(0, (self.height - scaled_h) // 2, self.width, scaled_h))
            if assets.bga_dark_texture:
                self.renderer.blit(assets.bga_dark_texture, pygame.Rect(0, 0, self.width, self.height))

    def draw_score_bar(self, p1_judgs, ai_judgs):
        def get_weighted_points(judgs):
            pts = judgs["PERFECT"] * 1.0 + judgs["GREAT"] * 0.7 + judgs["GOOD"] * 0.4 - judgs["MISS"] * 1.5
            return pts

        bar_w, bar_h = self.width, self._s(15)
        diff = get_weighted_points(p1_judgs) - get_weighted_points(ai_judgs)
        ratio = 0.5 + (diff / 500.0)
        ratio = max(0.01, min(0.99, ratio))
        mid_x = int(bar_w * ratio)

        self.renderer.draw_color = (0, 120, 255, 255)
        self.renderer.fill_rect((0, 0, mid_x, bar_h))
        self.renderer.draw_color = (255, 50, 50, 255)
        self.renderer.fill_rect((mid_x, 0, bar_w - mid_x, bar_h))
        self.renderer.draw_color = (255, 255, 255, 255)
        self.renderer.fill_rect((mid_x - 2, 0, 4, bar_h))

    def draw_effects(self, effects_list, lanes_x, lane_w):
        for eff in effects_list[:]:
            from .constants import EFFECT_EXPAND_SPEED, EFFECT_FADE_SPEED
            eff['radius'] += EFFECT_EXPAND_SPEED
            eff['alpha'] -= EFFECT_FADE_SPEED
            if eff['alpha'] <= 0:
                effects_list.remove(eff)
                continue
            
            note_type = eff.get('note_type', 0)
            r = self._s(eff['radius'])
            tx = lanes_x[eff['lane']] + lane_w // 2
            # Shift up by half of NOTE_H (20//2=10) to align with note head center
            ty = self._s(500 - 10) 
            
            if note_type == 0: # ── Bar Effect ──
                tex = self._get_bar_effect_texture(eff['color'], eff['alpha'], r, lane_w)
                self.renderer.blit(tex, pygame.Rect(tx - tex.width // 2, ty - tex.height // 2, tex.width, tex.height))
                
            else: # ── Circle Effect ──
                tex = self._get_circle_effect_texture(eff['color'], eff['alpha'], r)
                self.renderer.blit(tex, pygame.Rect(tx - r, ty - r, r*2, r*2))

    def draw_result(self, stats):
        def calc_score(judgs):
            return judgs["PERFECT"] * 1000 + judgs["GREAT"] * 500 + judgs["GOOD"] * 200

        score_h = calc_score(stats['judgments'])
        score_ai = calc_score(stats['ai_judgments']) if stats['mode'] == 'ai_multi' else 0

        # Background tint (GPU)
        self.renderer.draw_blend_mode = 1 # Blend
        self.renderer.draw_color = (20, 20, 35, 220)
        self.renderer.fill_rect((0, 0, self.width, self.height))

        if stats['mode'] == 'ai_multi':
            p1_win = score_h >= score_ai
            win_txt = "YOU WIN!" if p1_win else "AI BOT WINS"
            win_color = (0, 255, 255) if p1_win else (255, 50, 50)
            
            # Title
            t_tex = self._get_text_texture(stats['title'], True, (255, 255, 255), 255, size_override=self._s(40))
            self.renderer.blit(t_tex, pygame.Rect(self.width // 2 - t_tex.width // 2, self._s(10), t_tex.width, t_tex.height))
            
            # Win/Loss Banner
            bs_tex = self._get_text_texture(win_txt, True, win_color, 255, size_override=self._s(80))
            self.renderer.blit(bs_tex, pygame.Rect(self.width // 2 - bs_tex.width // 2, self._s(80), bs_tex.width, bs_tex.height))
        else:
            t_tex = self._get_text_texture("RESULT", True, (255, 255, 255), 255, size_override=self._s(64))
            self.renderer.blit(t_tex, pygame.Rect(self.width // 2 - t_tex.width // 2, self._s(50), t_tex.width, t_tex.height))

        y_start = self._s(220)
        p1_x = self._sx(100)
        
        # Player Section
        p1_title = self._get_text_texture("PLAYER", True, (100, 200, 255), 255)
        self.renderer.blit(p1_title, pygame.Rect(p1_x, y_start - self._s(40), p1_title.width, p1_title.height))

        y = y_start
        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            text = self._get_text_texture(f"{key}: {stats['judgments'][key]}", False, color, 255)
            self.renderer.blit(text, pygame.Rect(p1_x, y, text.width, text.height))
            y += self._s(50)
            
        combo_text = self._get_text_texture(f"MAX COMBO: {stats['max_combo']}", False, (255, 255, 255), 255)
        self.renderer.blit(combo_text, pygame.Rect(p1_x, y + self._s(20), combo_text.width, combo_text.height))
        score_text = self._get_text_texture(f"SCORE: {score_h:,}", True, (255, 255, 0), 255)
        self.renderer.blit(score_text, pygame.Rect(p1_x, y + self._s(70), score_text.width, score_text.height))

        if stats['mode'] == 'ai_multi':
            ai_x = self._sx(460)
            ai_title = self._get_text_texture("AI BOT", True, (255, 100, 100), 255)
            self.renderer.blit(ai_title, pygame.Rect(ai_x, y_start - self._s(40), ai_title.width, ai_title.height))
            
            y = y_start
            for key in JUDGMENT_ORDER:
                color = JUDGMENT_DEFS[key]["color"]
                ai_text = self._get_text_texture(f"{key}: {stats['ai_judgments'][key]}", False, color, 255)
                self.renderer.blit(ai_text, pygame.Rect(ai_x, y, ai_text.width, ai_text.height))
                y += self._s(50)
            ai_ct = self._get_text_texture(f"MAX COMBO: {stats['ai_max_combo']}", False, (255, 255, 255), 255)
            self.renderer.blit(ai_ct, pygame.Rect(ai_x, y + self._s(20), ai_ct.width, ai_ct.height))
            ai_score_text = self._get_text_texture(f"SCORE: {score_ai:,}", True, (255, 255, 0), 255)
            self.renderer.blit(ai_score_text, pygame.Rect(ai_x, y + self._s(70), ai_score_text.width, ai_score_text.height))
        else:
            right_x = self._sx(500)
            y = self._s(200)
            t_tex = self._get_text_texture(stats['title'], True, (255, 255, 255), 255, size_override=self._s(32))
            self.renderer.blit(t_tex, pygame.Rect(right_x, y, t_tex.width, t_tex.height))
            y += self._s(50)
            for key, label in [("artist", "Artist"), ("genre", "Genre"), ("level", "Level")]:
                val = stats['metadata'].get(key)
                if val and str(val) not in ('Unknown', '0'):
                    s = self._get_text_texture(f"{label}: {val}", False, (200, 220, 240), 255, size_override=self._s(24))
                    self.renderer.blit(s, pygame.Rect(right_x, y, s.width, s.height))
                    y += self._s(32)

        info_text = self._get_text_texture("Press ENTER or ESC to Return", False, (150, 150, 150), 255, size_override=self._s(20))
        self.renderer.blit(info_text, pygame.Rect(self.width // 2 - info_text.width // 2, self.height - self._s(40), info_text.width, info_text.height))
        # Note: Do NOT call present() here. RhythmGame.run calls it.

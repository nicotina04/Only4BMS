import time
import numpy as np
from .constants import JUDGMENT_DEFS, SONG_END_PADDING_MS

class GameEngine:
    def __init__(self, notes, bgms, bgas, hw_mult, play_sound_cb, set_judgment_cb, max_time, visual_timing_map=None):
        self.notes = notes
        self.bgms = bgms
        self.bgas = bgas
        self.hw_mult = hw_mult
        self.play_sound_cb = play_sound_cb
        self.set_judgment_cb = set_judgment_cb
        self.max_time = max_time
        self.visual_timing_map = visual_timing_map or [(0.0, 0.0, 1.0)]
        self.current_visual_time = 0.0
        
        self.current_bga_img = None
        self.state = "PLAYING"
        self.held_lns = [None] * 4 # lane -> active LN note
        self.bgm_idx = 0
        self.bga_idx = 0

    def process_hit(self, lane, current_time):
        max_window = JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult
        closest, min_diff = None, float('inf')

        for note in self.notes:
            if note['lane'] == lane and 'hit' not in note and 'miss' not in note and not note.get('is_auto'):
                diff = abs(note['time_ms'] - current_time)
                if diff < min_diff and diff <= max_window:
                    min_diff = diff
                    closest = note

        if closest:
            closest['hit'] = True
            for sid in closest['sample_ids']:
                self.play_sound_cb(sid)

            for key in ("PERFECT", "GREAT", "GOOD"):
                if min_diff <= JUDGMENT_DEFS[key]["threshold_ms"] * self.hw_mult:
                    self.set_judgment_cb(key, lane)
                    if closest.get('is_ln'):
                        self.held_lns[lane] = closest
                        closest['start_judgment'] = key
                    return True
        return False

    def process_release(self, lane, current_time):
        """Handle key release for long notes with full judgment range."""
        note = self.held_lns[lane]
        if not note:
            return

        diff = abs(note['end_time_ms'] - current_time)
        max_window = JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult
        
        # If released too early (outside window)
        if note['end_time_ms'] - current_time > max_window:
            note['miss'] = True
            self.set_judgment_cb("MISS", lane)
        else:
            # Lenient release: ignore exact timing, use the judgment from the start hit
            judgment = note.get('start_judgment', 'PERFECT')
            self.set_judgment_cb(judgment, lane)
            # Play release sounds if defined
            for sid in note.get('end_sample_ids', []):
                self.play_sound_cb(sid)
        
        self.held_lns[lane] = None
    
    def get_visual_time(self, current_real_time):
        """Calculate visual time (scroll position) from real time."""
        # Find segment in visual_timing_map where start_real <= current_real_time
        # [(start_real, start_visual, factor), ...] sorted by start_real
        best_seg = self.visual_timing_map[0]
        for seg in self.visual_timing_map:
            if seg[0] <= current_real_time:
                best_seg = seg
            else:
                break
        
        start_real, start_visual, factor = best_seg
        return start_visual + (current_real_time - start_real) * factor

    def update(self, current_time):
        self.current_visual_time = self.get_visual_time(current_time)
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult
        
        # Normal notes
        for note in self.notes:
            if 'hit' not in note and 'miss' not in note:
                if note.get('is_auto'):
                    if current_time >= note['time_ms']:
                        note['hit'] = True
                        for sid in note['sample_ids']:
                            self.play_sound_cb(sid)
                    continue

                if current_time - note['time_ms'] > miss_window:
                    note['miss'] = True
                    self.set_judgment_cb("MISS", note['lane'])
                elif current_time >= note['time_ms'] and self.held_lns[note['lane']]:
                    # Overlap with held LN: Treat as PERFECT hit
                    note['hit'] = True
                    for sid in note['sample_ids']:
                        self.play_sound_cb(sid)
                    self.set_judgment_cb("PERFECT", note['lane'])
        
        # Long notes - check for overdue release
        for lane, note in enumerate(self.held_lns):
            if note:
                # If held past the GOOD window, it's a MISS
                miss_limit = note['end_time_ms'] + (JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult)
                if current_time > miss_limit:
                    # Lenient auto-release: if held past the limit, just count as successful release
                    judgment = note.get('start_judgment', 'PERFECT')
                    self.set_judgment_cb(judgment, lane)
                    for sid in note.get('end_sample_ids', []):
                        self.play_sound_cb(sid)
                    self.held_lns[lane] = None

        # BGMs (Optimized index check)
        while self.bgm_idx < len(self.bgms):
            bgm = self.bgms[self.bgm_idx]
            if current_time >= bgm['time_ms']:
                self.play_sound_cb(bgm['sample_id'])
                self.bgm_idx += 1
            else:
                break

        # BGAs (Optimized index check)
        while self.bga_idx < len(self.bgas):
            bga = self.bgas[self.bga_idx]
            if current_time >= bga['time_ms']:
                self.current_bga_img = bga['bmp_id']
                self.bga_idx += 1
            else:
                break

        # End check
        if current_time > self.max_time + SONG_END_PADDING_MS:
            self.state = "RESULT"
            return True
        return False

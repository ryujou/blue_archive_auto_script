import time
from statistics import median

from core import color, image, picture
from core.exception import RequestHumanTakeOver
from core.utils import merge_nearby_coordinates
from module.activities.activity_utils import (
    check_sweep_availability, start_fight, to_mission_task_info, to_story_task_info,
)
from module.main_story import auto_fight


def _on_list(self, region):
    for i in range(3 if region == "mission" else 2):
        name = f"activity_{region}-chosen-{i}"
        if image.search_in_area(self, name, (680, 65, 1260, 145)):
            return True
    return False


def _select_list(self, region):
    self.update_screenshot_array()
    if _on_list(self, region):
        return True
    if not image.compare_image(self, "activity_menu"):
        self.logger.warning("Open the activity stage list in the game before running.")
        return False
    for i in range(3 if region == "mission" else 2):
        name = f"activity_{region}-not-chosen-{i}"
        point = image.search_in_area(self, name, (680, 65, 1260, 145))
        if point:
            self.click(point[0] + 40, point[1] + 19, duration=0.8, wait_over=True)
            self.update_screenshot_array()
            if _on_list(self, region):
                return True
    self.logger.warning(f"Cannot recognize the activity {region} tab.")
    return False


def _rows(self, region):
    positions = image.get_image_all_appear_position(
        self, f"activity_{region}-enter-task-button", (1060, 149, 1195, 686)
    )
    rows = []
    for group in merge_nearby_coordinates(positions, 5, 5):
        x = median(p[0] for p in group)
        y = median(p[1] for p in group)
        offsets = (-387, -6, 50, 28) if region == "story" else {
            "CN": (-384, -8, 43, 28),
            "JP": (-384, -8, 43, 28),
        }.get(self.identifier, (-384, 0, 43, 36))
        ox, oy, width, height = offsets
        text = self.ocr.get_region_res(
            baas=self, region=(x + ox, y + oy, x + ox + width, y + oy + height),
            language="en-us", candidates="0123456789l", filter_score=0.2,
        ).strip().replace("l", "1")
        if not text.isdigit() or int(text) <= 0:
            raise ValueError(f"Cannot read activity stage number: {text!r}")
        rows.append((int(text), int(x + 32), int(y + 22)))
    return sorted(set(rows))


def _page_key(rows):
    return tuple((number, round(y / 10)) for number, x, y in rows)


def _return_to_list(self, region):
    reactions = {
        "activity_task-info": (1128, 141),
        "main_story_episode-info": (917, 161),
        "activity_fight-success-confirm": (640, 663),
        "main_story_fight-confirm": (1168, 659),
        "normal_task_fight-confirm": (1168, 659),
        "normal_task_task-finish": (1038, 662),
        "normal_task_prize-confirm": (776, 655),
        "normal_task_reward-acquired-confirm": (800, 660),
        "normal_task_fight-complete-confirm": (1160, 666),
        "main_page_get-character": (640, 360),
        "main_page_full-notice": (887, 165),
        "activity_get-collectable-item1": (508, 505),
        "activity_get-collectable-item2": (505, 537),
        "plot_menu": (1205, 34),
        "plot_skip-plot-button": (1213, 116),
        "plot_skip-plot-notice": (766, 520),
    }
    deadline = time.monotonic() + 600
    while self.flag_run:
        self.update_screenshot_array()
        if picture.match_img_feature(self, "normal_task_fail-confirm"):
            self.logger.warning("Battle failed; stopped at the current stage.")
            return False
        if picture.match_any_img_feature(self, ["purchase_ap_notice", "purchase_ap_notice-localized"]):
            self.logger.warning("Not enough AP; activity progression stopped.")
            return False
        if _on_list(self, region) or (
            image.compare_image(self, "activity_menu") and _select_list(self, region)
        ):
            time.sleep(0.8)
            self.update_screenshot_array()
            return True
        for name, point in reactions.items():
            if picture.match_img_feature(self, name):
                self.click(*point, duration=0.5, wait_over=True)
                break
        else:
            if color.match_rgb_feature(self, "reward_acquired"):
                self.click(640, 100, duration=0.5, wait_over=True)
        if time.monotonic() > deadline:
            self.logger.warning("Could not return to the activity list.")
            return False
        time.sleep(self.screenshot_interval)
    raise RequestHumanTakeOver


def _open_stage(self, x, y):
    return picture.co_detect(
        self, img_ends=["activity_task-info", "main_story_episode-info"],
        img_reactions={"activity_menu": (x, y)}, time_out=30,
    )


def _start_stage(self):
    result = picture.co_detect(
        self,
        rgb_ends=["formation_edit1", "reward_acquired"],
        rgb_reactions={f"formation_edit{i}": (151, 387) for i in (2, 3, 4)},
        img_ends=["activity_unit-formation", "activity_formation", "activity_self-formation",
                  "purchase_ap_notice", "purchase_ap_notice-localized"],
        img_reactions={
            "activity_task-info": (940, 538),
            "main_story_episode-info": (629, 518),
            "main_page_get-character": (640, 360),
            "plot_menu": (1205, 34),
            "plot_skip-plot-button": (1213, 116),
            "plot_skip-plot-notice": (766, 520),
        },
        time_out=120,
    )
    if result in ("purchase_ap_notice", "purchase_ap_notice-localized"):
        self.logger.warning("Not enough AP; activity progression stopped.")
        return False
    if result != "reward_acquired":
        if any(color.match_rgb_feature(self, f"formation_edit{i}") for i in (2, 3, 4)):
            self.click(151, 387, duration=0.5, wait_over=True)
        start_fight(self, 1)
        auto_fight(self)
    return "reward_acquired" if result == "reward_acquired" else True


def implement(self, region):
    if not _select_list(self, region):
        return False
    self.logger.info(f"Progressing current activity {region}; battle team 1.")
    previous = None
    while self.flag_run:
        rows = _rows(self, region)
        key = _page_key(rows)
        if key == previous:
            break
        previous = key
        self.swipe(907, 260, 907, 460, duration=0.5, post_sleep_time=0.8)
        self.update_screenshot_array()

    completed = set()
    previous = None
    while self.flag_run:
        self.update_screenshot_array()
        rows = _rows(self, region)
        if not rows:
            self.logger.warning("No accessible activity stage buttons recognized.")
            return False
        pending = [row for row in rows if row[0] not in completed]
        if not pending:
            key = _page_key(rows)
            if key == previous:
                missing = set(range(1, max(completed) + 1)) - completed
                if missing:
                    self.logger.warning(f"Stage numbers not checked: {sorted(missing)}; stopped.")
                    return False
                self.logger.info("All accessible activity stages completed.")
                return True
            previous = key
            self.swipe(907, 460, 907, 260, duration=0.5, post_sleep_time=0.8)
            continue
        number, x, y = pending[0]
        self.logger.info(f"Check activity {region} stage {number}.")
        plot = _open_stage(self, x, y)
        status = check_sweep_availability(self, plot)
        if status == "unknown":
            self.logger.warning(f"Cannot recognize stage {number} completion state; stopped.")
            _return_to_list(self, region)
            return False
        if status != "sss":
            stage_result = _start_stage(self)
            if not stage_result:
                return False
            if not _return_to_list(self, region):
                return False
            if stage_result != "reward_acquired":
                current = next((row for row in _rows(self, region) if row[0] == number), None)
                if current is None:
                    open_task = to_story_task_info if region == "story" else to_mission_task_info
                    visible_rows = _rows(self, region)
                    total = max([number] + [row[0] for row in visible_rows])
                    plot = open_task(self, number, total)
                else:
                    plot = _open_stage(self, current[1], current[2])
                if check_sweep_availability(self, plot) != "sss":
                    self.logger.warning(f"Stage {number} is not complete/three-star; stopped.")
                    _return_to_list(self, region)
                    return False
        completed.add(number)
        if not _return_to_list(self, region):
            return False
    raise RequestHumanTakeOver

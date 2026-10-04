from core import picture


def implement(self):
    if self.server != "JP":
        self.logger.info("Tour attendance is only available on JP.")
        return True

    self.to_main_page()
    picture.co_detect(
        self,
        rgb_reactions={"main_page": (222, 136)},
        img_ends="tour_attendance_menu",
        time_out=60,
    )
    picture.co_detect(
        self,
        img_reactions={"tour_attendance_menu": (128, 219)},
        img_ends="tour_attendance_tour",
        time_out=60,
    )
    result = picture.co_detect(
        self,
        img_reactions={"tour_attendance_claim": (1147, 674)},
        img_ends=["tour_attendance_reward", "tour_attendance_claimed"],
        time_out=60,
    )
    if result == "tour_attendance_reward":
        self.logger.info("Tour attendance reward acquired.")
        picture.co_detect(
            self,
            img_reactions={"tour_attendance_reward": (640, 630)},
            img_ends="tour_attendance_claimed",
            time_out=60,
        )
    else:
        self.logger.info("Tour attendance reward already collected.")
    self.to_main_page()
    return True


from src.common.queries import HangmanSQL

from src.structs.leaderboard import TextLeaderboardBase


class HangmanLeaderboard(TextLeaderboardBase):
    def __init__(self):
        super(HangmanLeaderboard, self).__init__(
            title="Top Hangman Players",
            query=HangmanSQL.SELECT_LEADERBOARD,
            columns=["wins"],
            order_col="wins",
            max_rows=15
        )
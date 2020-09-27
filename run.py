
def set_env():
    from configparser import ConfigParser

    config = ConfigParser()

    config.read("config.ini")

    os.environ["DEBUG"] = "1"

    os.environ["VOTE_AUTH"] = config.get("bot", "VOTE_AUTH")

    os.environ["BOT_TOKEN"] = config.get("bot", "TOKEN")
    os.environ["DBL_TOKEN"] = config.get("api", "DBL_TOKEN")
    os.environ["MONGO_STR"] = config.get("database", "MONGO_STR")

    os.environ["RAID_API_KEY"] = config.get("api", "RAID_API_KEY")


def setup_loop():
    import sys
    import subprocess
    import platform

    if platform.system() == "Linux":
        try:
            import uvloop
        except ImportError:
            if subprocess.check_call([sys.executable, "-m", "pip", "install", 'uvloop']) == 0:
                import uvloop

        uvloop.install()


if __name__ == "__main__":
    import os
    import src

    if os.path.isfile("config.ini"):
        set_env()

    setup_loop()

    src.run()

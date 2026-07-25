from apscheduler.schedulers.blocking import BlockingScheduler
from collector import collect_once

scheduler = BlockingScheduler(timezone="Asia/Seoul")

scheduler.add_job(collect_once, "interval", minutes=10, id="collect_congestion")

if __name__ == "__main__":
    print("스케줄러 시작 - 10분마다 혼잡도 수집")
    collect_once()  # 시작 즉시 1회 수집
    scheduler.start()


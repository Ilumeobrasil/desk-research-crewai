import time

class Console:
    _timers = {}

    @staticmethod
    def time(label: str):
        Console._timers[label] = time.perf_counter()

    @staticmethod
    def time_end(label: str):
        if label not in Console._timers:
            raise ValueError(f"Timer '{label}' não existe")

        elapsed = time.perf_counter() - Console._timers.pop(label)

        minutes, seconds = divmod(elapsed, 60)

        if minutes >= 1:
            print(f"{label}: {int(minutes)}m {seconds:05.2f}s")
        else:
            print(f"{label}: {seconds:.4f}s")
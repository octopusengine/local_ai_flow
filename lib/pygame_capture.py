"""Child-process harness: capture a software Pygame display without editing the game."""

from pathlib import Path
import runpy
import sys


def main() -> None:
    import pygame

    source, output, frame = sys.argv[1:4]
    target_frame = int(frame)
    sys.argv = [source, *sys.argv[4:]]
    sys.path.insert(0, str(Path(source).resolve().parent))
    count = 0

    def wrap(present):
        def capture(*args, **kwargs):
            nonlocal count
            result = present(*args, **kwargs)
            # update(None) explicitly requests no display update.
            if args == (None,):
                return result
            count += 1
            if count >= target_frame:
                surface = pygame.display.get_surface()
                if surface is None or surface.get_flags() & pygame.OPENGL:
                    raise RuntimeError("Capture requires a software Pygame display.")
                pygame.image.save(surface, output)
                print(f"Captured display update {count} ({surface.get_width()}x{surface.get_height()}).")
                raise SystemExit(0)
            return result
        return capture

    pygame.display.flip = wrap(pygame.display.flip)
    pygame.display.update = wrap(pygame.display.update)
    try:
        runpy.run_path(source, run_name="__main__")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

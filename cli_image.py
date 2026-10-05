import argparse
import json
import random
import sys
from pathlib import Path

import torch
from PIL import Image
from diffusers import QwenImage21Pipeline


CONFIG_FILE = "cli_image.json"
VERSION = "v0.76"

INPUT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
}

OUTPUT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
}


# ============================================================
# CONFIG
# ============================================================

def load_config():
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_FILE}"
        )

    if not config_path.is_file():
        raise ValueError(
            f"Configuration path is not a file: {CONFIG_FILE}"
        )

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in {CONFIG_FILE}: "
            f"line {e.lineno}, column {e.colno}: {e.msg}"
        ) from e

    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration root must be a JSON object: "
            f"{CONFIG_FILE}"
        )

    return config


def get_required_config(config, key):
    value = config.get(key)

    if value is None:
        raise ValueError(
            f"Missing required configuration value: '{key}'"
        )

    return value


# ============================================================
# SEED
# ============================================================

def get_seed(seed, index):
    if seed is not None:
        return seed + index

    return random.randint(0, 2**32 - 1)


# ============================================================
# PATHS
# ============================================================

def get_edit_output_name(path, suffix="e"):
    """
    PICT1325.jpg -> PICT1325_e.jpg   (default)
    PICT1325.jpg -> PICT1325_j.jpg   (with -x j)

    The suffix is inserted before the file extension.
    """

    suffix = str(suffix).strip().lstrip("_")

    if not suffix:
        raise ValueError("Edit suffix cannot be empty.")

    return Path(
        f"{path.stem}_{suffix}{path.suffix.lower()}"
    )


def is_already_edited(path, suffix="e"):
    """
    image_e.png -> True   (default)
    image_j.png -> False  (when suffix is 'e')
    """

    suffix = str(suffix).strip().lstrip("_")

    if not suffix:
        return False

    return path.stem.lower().endswith(f"_{suffix.lower()}")


def get_output_path(output_name, output_format, index, num_images):
    """Build output path; omit _1 when only one image is requested."""
    if num_images == 1:
        return Path(f"{output_name}.{output_format}")
    return Path(f"{output_name}{index + 1}.{output_format}")


def validate_input_image(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Input image not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Input path is not a file: {path}"
        )

    if path.suffix.lower() not in INPUT_EXTENSIONS:
        raise ValueError(
            f"Unsupported input image format: "
            f"{path.suffix}. "
            f"Supported: PNG, JPG, JPEG"
        )


# ============================================================
# IMAGE IO
# ============================================================

def load_image(path):
    """
    Načte obrázek a normalizuje ho na RGB.

    Model tak dostává konzistentní vstup
    bez ohledu na původní PNG/JPEG režim.
    """

    try:
        with Image.open(path) as image:
            image.load()

            return image.convert("RGB")

    except Exception as e:
        raise RuntimeError(
            f"Cannot load image '{path}': {e}"
        ) from e


def save_image(image, output_path):
    """
    Bezpečné uložení podle přípony.

    JPEG/JPG:
        vždy RGB.

    PNG:
        zachová RGB/RGBA.
    """

    suffix = output_path.suffix.lower()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if suffix in {".jpg", ".jpeg"}:

        image = image.convert("RGB")

        image.save(
            output_path,
            format="JPEG",
            quality=95,
            optimize=True,
        )

    elif suffix == ".png":

        if image.mode not in {
            "RGB",
            "RGBA",
        }:
            image = image.convert("RGBA")

        image.save(
            output_path,
            format="PNG",
            optimize=True,
        )

    else:
        raise ValueError(
            f"Unsupported output format: {suffix}"
        )


# ============================================================
# DEVICE / DTYPE
# ============================================================

def validate_device(device):

    if device == "mps":

        if not torch.backends.mps.is_available():
            raise RuntimeError(
                "MPS is not available on this system."
            )

    elif device == "cuda":

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available on this system."
            )

    elif device != "cpu":

        raise ValueError(
            f"Unsupported device: {device}. "
            f"Supported: mps, cuda, cpu"
        )


def get_dtype(dtype_name):

    dtype_map = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }

    if dtype_name not in dtype_map:
        raise ValueError(
            f"Unsupported dtype: {dtype_name}. "
            f"Supported: {', '.join(dtype_map.keys())}"
        )

    return dtype_map[dtype_name]


# ============================================================
# MODEL
# ============================================================

def load_pipeline(
    model_path,
    dtype,
    device,
):

    print("Loading model...")

    pipe = QwenImage21Pipeline.from_pretrained(
        model_path,
        dtype=dtype,
    )

    pipe = pipe.to(device)

    print("Model loaded.")
    print()

    return pipe


# ============================================================
# PIPELINE OPERATIONS
# ============================================================

def generate_image(
    pipe,
    prompt,
    width,
    height,
    steps,
    generator,
):

    result = pipe(
        prompt=prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        generator=generator,
    )

    return result.images[0]


def build_sigmas(steps, strength):
    """
    Map our user-facing strength (0..1) to a Qwen sigma schedule.

    QwenImage21Pipeline has no native `strength` argument. It does expose
    custom `sigmas`, so strength is implemented as a Qwen-specific control
    over the initial denoising sigma.

    strength=1.0 -> default Qwen schedule
    lower strength -> lower initial sigma / weaker stochastic variation

    This is not the classic Stable Diffusion img2img strength parameter.
    """

    if strength is None or strength == 1.0:
        return None

    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength must be between 0.0 and 1.0")

    final_sigma = 1.0 / steps
    start_sigma = max(float(strength), final_sigma)

    return torch.linspace(
        start_sigma,
        final_sigma,
        steps,
        dtype=torch.float32,
    ).tolist()


def edit_image(
    pipe,
    prompt,
    input_image,
    steps,
    strength,
    generator,
):
    sigmas = build_sigmas(steps, strength)

    kwargs = {
        "prompt": prompt,
        "image": input_image,
        "generator": generator,
    }

    if sigmas is None:
        kwargs["num_inference_steps"] = steps
    else:
        # QwenImage21Pipeline requires num_inference_steps=None
        # when a custom sigma schedule is supplied.
        kwargs["sigmas"] = sigmas

    result = pipe(**kwargs)

    return result.images[0]


def merge_images(
    pipe,
    prompt,
    input_images,
    width,
    height,
    steps,
    strength,
    generator,
):
    """
    Multi-reference generation.

    input_images je seznam PIL.Image objektů.
    """

    sigmas = build_sigmas(steps, strength)

    kwargs = {
        "prompt": prompt,
        "image": input_images,
        "width": width,
        "height": height,
        "generator": generator,
    }

    if sigmas is None:
        kwargs["num_inference_steps"] = steps
    else:
        kwargs["sigmas"] = sigmas

    result = pipe(**kwargs)

    return result.images[0]


# ============================================================
# ARGUMENTS
# ============================================================

def create_parser():

    parser = argparse.ArgumentParser(
        description=(
            f"Generate or edit images using Qwen-Image-2.1 "
            f"(version {VERSION})"
        )
    )

    parser.add_argument(
        "-N",
        type=int,
        default=None,
        help="Number of images to generate/edit (default: 1)",
    )

    parser.add_argument(
        "-p",
        "--prompt",
        default=None,
        help=(
            "Prompt text or path to a text file. "
            "If omitted, use prompt_file from config."
        ),
    )

    parser.add_argument(
        "-b",
        "--base",
        default=None,
        help=(
            "Base prompt text or path to a text file. "
            "Prepended to the prompt with a blank line when provided."
        ),
    )

    parser.add_argument(
        "-f",
        "--file",
        default=None,
        help="Base filename for generated output files",
    )

    parser.add_argument(
        "-n",
        "--name",
        default=None,
        help="Override output.name from config",
    )

    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=None,
        help="Override seed from config",
    )

    parser.add_argument(
        "-t",
        "--steps",
        type=int,
        default=None,
        help="Override number of inference steps",
    )

    parser.add_argument(
        "-r",
        "--strength",
        type=float,
        default=None,
        metavar="0..1",
        help="Override edit strength (0.0-1.0)",
    )

    parser.add_argument(
        "-W",
        "--width",
        type=int,
        default=None,
        help="Override generation width",
    )

    parser.add_argument(
        "-H",
        "--height",
        type=int,
        default=None,
        help="Override generation height",
    )

    parser.add_argument(
        "-e",
        "--edit",
        type=str,
        default=None,
        metavar="IMAGE",
        help="Edit a specific input image",
    )

    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Edit all PNG/JPG/JPEG images from ./src and save to ./dest",
    )

    parser.add_argument(
        "-x",
        "--suffix",
        default="e",
        help="Suffix for --all output filenames before extension (default: e)",
    )

    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help="Combine all PNG/JPG/JPEG images from ./src into one generated image",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    return parser


# ============================================================
# MAIN
# ============================================================

def _text_quality_score(text):
    """Score decoded text for likely mojibake / encoding corruption."""
    if not text:
        return 0.0

    suspicious = (
        "Ã", "Â", "â", "ð", "Ð", "Ñ", "�",
        "Ï", "ﬁ", "ﬂ", "Œ", "œ", "Š", "Ž", "š", "ž",
    )
    bad = sum(text.count(ch) for ch in suspicious)
    bad += text.count("�") * 10

    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text)
    ratio = printable / max(len(text), 1)

    return ratio - (bad / max(len(text), 1)) * 3.0


def _try_repair_mojibake(text):
    """Try common UTF-8/legacy mojibake repairs and keep the best result."""
    candidates = [text]

    for source_encoding in ("cp1252", "latin1", "mac_roman"):
        try:
            repaired = text.encode(source_encoding).decode("utf-8")
            candidates.append(repaired)
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return max(candidates, key=_text_quality_score)



def resolve_text_or_file(value):
    """Safely distinguish literal text from an existing prompt/base file."""
    if value is None:
        return False, None

    value = str(value)

    # Multiline values are literal text, never filesystem paths.
    if "\n" in value or "\r" in value:
        return False, None

    try:
        candidate = Path(value)
        try:
            return candidate.is_file(), candidate if candidate.is_file() else None
        except OSError:
            # Includes [Errno 63] File name too long.
            return False, None
    except (OSError, ValueError):
        return False, None


def read_prompt_file(path):
    """
    Read a prompt on Windows, Linux or macOS.

    Strategy:
      1. UTF-8 BOM / UTF-8
      2. Common Central-European Windows encodings
      3. macOS legacy encoding
      4. Mojibake repair when the decoded result looks corrupted

    Returns: (text, encoding_description)
    """
    path = Path(path)
    data = path.read_bytes()

    candidates = []

    if data.startswith(b"\xef\xbb\xbf"):
        try:
            candidates.append(("utf-8-sig", data.decode("utf-8-sig")))
        except UnicodeDecodeError:
            pass

    try:
        candidates.append(("utf-8", data.decode("utf-8")))
    except UnicodeDecodeError:
        pass

    for encoding in ("cp1250", "cp1252"):
        try:
            candidates.append((encoding, data.decode(encoding)))
        except UnicodeDecodeError:
            pass

    try:
        candidates.append(("mac_roman", data.decode("mac_roman")))
    except UnicodeDecodeError:
        pass

    if not candidates:
        raise UnicodeError(
            f"Cannot decode prompt file '{path}'. "
            "Supported encodings: UTF-8, UTF-8 BOM, CP1250, CP1252, MacRoman."
        )

    encoding, text = max(
        candidates,
        key=lambda item: _text_quality_score(item[1])
    )

    repaired = _try_repair_mojibake(text)
    repaired_score = _text_quality_score(repaired)
    original_score = _text_quality_score(text)

    if repaired_score > original_score + 0.02:
        return repaired.strip(), f"{encoding} -> repaired UTF-8 mojibake"

    return text.strip(), encoding


def main():

    parser = create_parser()

    args = parser.parse_args()

    # --------------------------------------------------------
    # CLI validation
    # --------------------------------------------------------

    active_modes = sum(
        [
            args.edit is not None,
            args.all,
            args.merge,
        ]
    )

    if active_modes > 1:
        parser.error(
            "-e/--edit, -a/--all and "
            "-m/--merge are mutually exclusive"
        )

    if args.N is not None and args.N < 1:
        parser.error(
            "-N must be at least 1"
        )

    if args.steps is not None and args.steps < 1:
        parser.error(
            "-t/--steps must be at least 1"
        )

    if args.width is not None and args.width < 1:
        parser.error(
            "-W/--width must be at least 1"
        )

    if args.height is not None and args.height < 1:
        parser.error(
            "-H/--height must be at least 1"
        )

    if args.strength is not None and not 0.0 <= args.strength <= 1.0:
        parser.error(
            "--strength must be between 0.0 and 1.0"
        )

    if not args.suffix.strip().lstrip("_"):
        parser.error(
            "-x/--suffix cannot be empty"
        )

    # --------------------------------------------------------
    # Config
    # --------------------------------------------------------

    config = load_config()

    model_path = Path(
        get_required_config(
            config,
            "model",
        )
    )

    prompt_file = Path(
        get_required_config(
            config,
            "prompt_file",
        )
    )

    input_config = config.get(
        "input",
        {},
    )

    output_config = config.get(
        "output",
        {},
    )

    generation_config = config.get(
        "generation",
        {},
    )

    # --------------------------------------------------------
    # Model path
    # --------------------------------------------------------

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model path not found: {model_path}"
        )

    if not model_path.is_dir():
        raise ValueError(
            f"Model path is not a directory: {model_path}"
        )

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    if args.prompt is not None:
        prompt_is_file, prompt_arg = resolve_text_or_file(args.prompt)

        if prompt_is_file:
            prompt, prompt_encoding = read_prompt_file(prompt_arg)
            if not prompt:
                raise ValueError(
                    f"Prompt file is empty: {prompt_arg}"
                )
        else:
            prompt = str(args.prompt).strip()

        if not prompt:
            raise ValueError("Prompt cannot be empty.")
    else:
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_file}"
            )

        prompt, prompt_encoding = read_prompt_file(prompt_file)

        if not prompt:
            raise ValueError(
                f"Prompt file is empty: {prompt_file}"
            )

    if args.base is not None:
        base_is_file, base_arg = resolve_text_or_file(args.base)

        if base_is_file:
            base_prompt, base_encoding = read_prompt_file(base_arg)
            if not base_prompt:
                raise ValueError(
                    f"Base prompt file is empty: {base_arg}"
                )
        else:
            base_prompt = str(args.base).strip()

        if not base_prompt:
            raise ValueError("Base prompt cannot be empty.")

        prompt = f"{base_prompt}\n\n{prompt}"

    # --------------------------------------------------------
    # Generation config
    # --------------------------------------------------------

    width = generation_config.get(
        "width",
        1024,
    )

    height = generation_config.get(
        "height",
        1024,
    )

    num_inference_steps = generation_config.get(
        "num_inference_steps",
        30,
    )

    config_seed = generation_config.get(
        "seed",
        None,
    )

    config_strength = generation_config.get(
        "strength",
        1.0,
    )

    # --------------------------------------------------------
    # Validate generation config
    # --------------------------------------------------------

    if not isinstance(width, int) or width < 1:
        raise ValueError(
            f"Invalid generation.width: {width}"
        )

    if not isinstance(height, int) or height < 1:
        raise ValueError(
            f"Invalid generation.height: {height}"
        )

    if (
        not isinstance(
            num_inference_steps,
            int,
        )
        or num_inference_steps < 1
    ):
        raise ValueError(
            "generation.num_inference_steps "
            "must be an integer >= 1"
        )

    if (
        not isinstance(config_strength, (int, float))
        or not 0.0 <= float(config_strength) <= 1.0
    ):
        raise ValueError(
            "generation.strength must be between 0.0 and 1.0"
        )

    strength = float(config_strength)

    # --------------------------------------------------------
    # CLI overrides
    # --------------------------------------------------------

    num_images = (
        args.N
        if args.N is not None
        else 1
    )

    output_name = output_config.get(
        "name",
        "output",
    )

    output_format = output_config.get(
        "format",
        "png",
    )

    output_format = (
        output_format
        .lower()
        .lstrip(".")
    )

    seed = (
        args.seed
        if args.seed is not None
        else config_seed
    )

    if args.steps is not None:
        num_inference_steps = args.steps

    if args.width is not None:
        width = args.width

    if args.height is not None:
        height = args.height

    if args.strength is not None:
        strength = args.strength

    if args.file is not None:
        output_name = args.file

    if args.name is not None:
        output_name = args.name

    # --------------------------------------------------------
    # Validate output
    # --------------------------------------------------------

    if output_format not in {
        "png",
        "jpg",
        "jpeg",
    }:
        raise ValueError(
            f"Unsupported output.format: "
            f"{output_format}. "
            f"Supported: png, jpg, jpeg"
        )

    if not output_name:
        raise ValueError(
            "Output name cannot be empty."
        )

    output_display_name = (
        f"{output_name}.{output_format}"
        if num_images == 1
        else f"{output_name}1.{output_format}"
    )

    # --------------------------------------------------------
    # Device / dtype
    # --------------------------------------------------------

    device = config.get(
        "device",
        "mps",
    )

    dtype_name = config.get(
        "dtype",
        "bfloat16",
    )

    validate_device(device)

    dtype = get_dtype(
        dtype_name
    )

    # --------------------------------------------------------
    # Determine mode
    #
    # Editing is activated ONLY explicitly by:
    #   -m / --merge
    #   -a / --all
    #   -e / --edit
    #
    # input.edit_file is only the default input path for -e;
    # it must never activate edit mode by itself.
    # --------------------------------------------------------

    config_edit_file = input_config.get(
        "edit_file"
    )

    if args.merge:

        mode = "MERGE"

    elif args.all:

        mode = "EDIT ALL"

    elif args.edit is not None:

        mode = "EDIT"

    else:

        mode = "GENERATE"

    merge_mode = mode == "MERGE"
    all_mode = mode == "EDIT ALL"
    edit_mode = mode == "EDIT"

    # --------------------------------------------------------
    # Input directories
    # --------------------------------------------------------

    src_dir = Path("./src")
    dest_dir = Path("./dest")

    input_files = []

    # ========================================================
    # MERGE
    # ========================================================

    if merge_mode:

        if not src_dir.exists():
            raise FileNotFoundError(
                f"Source directory not found: {src_dir}"
            )

        if not src_dir.is_dir():
            raise ValueError(
                f"Source path is not a directory: {src_dir}"
            )

        input_files = sorted(
            path
            for path in src_dir.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in INPUT_EXTENSIONS
                and not is_already_edited(path)
            )
        )

        if not input_files:
            raise FileNotFoundError(
                f"No input images found in {src_dir}"
            )

        # Qwen-Image 2.1 supports up to 10
        # reference images.
        if len(input_files) > 10:
            raise ValueError(
                f"Merge mode found {len(input_files)} "
                f"images in {src_dir}, but Qwen-Image 2.1 "
                f"supports up to 10 reference images."
            )

    # ========================================================
    # EDIT ALL
    # ========================================================

    elif all_mode:

        if not src_dir.exists():
            raise FileNotFoundError(
                f"Source directory not found: {src_dir}"
            )

        if not src_dir.is_dir():
            raise ValueError(
                f"Source path is not a directory: {src_dir}"
            )

        dest_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        input_files = sorted(
            path
            for path in src_dir.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in INPUT_EXTENSIONS
                and not is_already_edited(path)
            )
        )

        if not input_files:
            raise FileNotFoundError(
                f"No input images found in {src_dir}"
            )

    # ========================================================
    # EDIT SINGLE
    # ========================================================

    elif edit_mode:

        edit_file = (
            args.edit
            if args.edit is not None
            else config_edit_file
        )

        if not edit_file:
            raise ValueError(
                "No edit image specified."
            )

        input_path = Path(
            edit_file
        )

        validate_input_image(
            input_path
        )

        input_files = [
            input_path
        ]

    # ========================================================
    # DISPLAY CONFIGURATION
    # ========================================================

    print()
    print("========================================")
    print("Qwen-Image-2.1")
    print(f"Version: {VERSION}")
    print("========================================")

    print(
        f"Mode:   {mode}"
    )

    print(
        f"Model:  {model_path}"
    )

    print(
        f"Device: {device}"
    )

    print(
        f"Dtype:  {dtype_name}"
    )

    print()

    print("Generation:")

    print(
        f"  Steps: {num_inference_steps}"
    )

    print(
        "  Seed:  "
        f"{seed if seed is not None else 'random'}"
    )

    print(
        f"  Strength: {strength}"
    )

    print(
        f"  Size:  {width}x{height}"
    )

    if merge_mode:

        print(
            "  Input:  ./src"
        )

        print(
            f"  Images: {len(input_files)}"
        )

        print(
            f"  Output: {output_display_name}"
        )

    elif all_mode:

        print(
            "  Input:  ./src"
        )

        print(
            "  Output: ./dest"
        )

        print(
            f"  Suffix: _{args.suffix.strip().lstrip('_')}"
        )

        print(
            f"  Files:  {len(input_files)}"
        )

    elif edit_mode:

        print(
            f"  Input:  {input_files[0]}"
        )

        print(
            f"  Output: {output_display_name}"
        )

    else:

        print(
            f"  Output: {output_display_name}"
        )

    if mode == "GENERATE" and strength != 1.0:
        print(
            "  Note: strength is ignored in normal text-to-image mode."
        )

    print(
        "========================================"
    )

    print()

    print("Prompt:")
    print(prompt)
    print()

    # ========================================================
    # LOAD MODEL
    # ========================================================

    pipe = load_pipeline(
        model_path,
        dtype,
        device,
    )

    # ========================================================
    # MERGE
    # ========================================================

    if merge_mode:

        print(
            f"Loading {len(input_files)} "
            f"reference image(s)..."
        )

        reference_images = []

        for index, input_path in enumerate(
            input_files
        ):

            print(
                f"  <image{index + 1}> "
                f"{input_path.name}"
            )

            reference_images.append(
                load_image(input_path)
            )

        print()

        success_count = 0

        for i in range(num_images):

            current_seed = get_seed(
                seed,
                i,
            )

            output_path = get_output_path(
                output_name, output_format, i, num_images
            )

            print(
                f"[{i + 1}/{num_images}] "
                f"Merging {len(reference_images)} "
                f"reference images..."
            )

            print(
                f"  Seed: {current_seed}"
            )

            print(
                f"  Output: {output_path}"
            )

            try:

                generator = torch.Generator(
                    device=device
                ).manual_seed(
                    current_seed
                )

                result_image = merge_images(
                    pipe=pipe,
                    prompt=prompt,
                    input_images=reference_images,
                    width=width,
                    height=height,
                    steps=num_inference_steps,
                    strength=strength,
                    generator=generator,
                )

                save_image(
                    result_image,
                    output_path,
                )

                success_count += 1

                print(
                    "  Done."
                )

            except KeyboardInterrupt:

                print()
                print(
                    "Interrupted by user."
                )

                raise

            except Exception as e:

                print(
                    f"  ERROR: {e}"
                )

            print()

        print(
            f"Done. Generated "
            f"{success_count}/{num_images} "
            f"merged image(s)."
        )

        if success_count != num_images:
            sys.exit(1)

        return

    # ========================================================
    # EDIT ALL
    # ========================================================

    if all_mode:

        success_count = 0
        error_count = 0

        print(
            f"Processing {len(input_files)} image(s)..."
        )

        print()

        for index, input_path in enumerate(
            input_files
        ):

            print(
                f"[{index + 1}/{len(input_files)}] "
                f"{input_path.name}"
            )

            current_seed = get_seed(
                seed,
                index,
            )

            output_path = (
                dest_dir
                / get_edit_output_name(
                    input_path,
                    args.suffix,
                )
            )

            print(
                f"  Seed: {current_seed}"
            )

            print(
                f"  Output: {output_path}"
            )

            try:

                generator = torch.Generator(
                    device=device
                ).manual_seed(
                    current_seed
                )

                input_image = load_image(
                    input_path
                )

                result_image = edit_image(
                    pipe=pipe,
                    prompt=prompt,
                    input_image=input_image,
                    steps=num_inference_steps,
                    strength=strength,
                    generator=generator,
                )

                save_image(
                    result_image,
                    output_path,
                )

                success_count += 1

                print(
                    "  Done."
                )

            except KeyboardInterrupt:

                print()
                print(
                    "Interrupted by user."
                )

                raise

            except Exception as e:

                error_count += 1

                print(
                    f"  ERROR: {e}"
                )

            print()

        print(
            "========================================"
        )

        print(
            "Finished"
        )

        print(
            "========================================"
        )

        print(
            f"Successful: {success_count}"
        )

        print(
            f"Errors:     {error_count}"
        )

        print(
            f"Total:      {len(input_files)}"
        )

        print(
            "========================================"
        )

        if error_count > 0:
            sys.exit(1)

        return

    # ========================================================
    # EDIT SINGLE
    # ========================================================

    if edit_mode:

        input_path = input_files[0]

        print(
            f"Input: {input_path}"
        )

        input_image = load_image(
            input_path
        )

        print(
            f"Input size: "
            f"{input_image.width}x"
            f"{input_image.height}"
        )

        print()

        success_count = 0

        for i in range(num_images):

            current_seed = get_seed(
                seed,
                i,
            )

            output_path = get_output_path(
                output_name, output_format, i, num_images
            )

            print(
                f"[{i + 1}/{num_images}] "
                f"Editing..."
            )

            print(
                f"  Seed: {current_seed}"
            )

            print(
                f"  Output: {output_path}"
            )

            try:

                generator = torch.Generator(
                    device=device
                ).manual_seed(
                    current_seed
                )

                result_image = edit_image(
                    pipe=pipe,
                    prompt=prompt,
                    input_image=input_image,
                    steps=num_inference_steps,
                    strength=strength,
                    generator=generator,
                )

                save_image(
                    result_image,
                    output_path,
                )

                success_count += 1

                print(
                    "  Done."
                )

            except KeyboardInterrupt:

                print()
                print(
                    "Interrupted by user."
                )

                raise

            except Exception as e:

                print(
                    f"  ERROR: {e}"
                )

            print()

        print(
            f"Done. Generated "
            f"{success_count}/{num_images} "
            f"image(s)."
        )

        if success_count != num_images:
            sys.exit(1)

        return

    # ========================================================
    # NORMAL GENERATION
    # ========================================================

    success_count = 0

    for i in range(num_images):

        current_seed = get_seed(
            seed,
            i,
        )

        output_path = get_output_path(
            output_name, output_format, i, num_images
        )

        print(
            f"[{i + 1}/{num_images}] "
            f"Generating..."
        )

        print(
            f"  Seed: {current_seed}"
        )

        print(
            f"  Output: {output_path}"
        )

        try:

            generator = torch.Generator(
                device=device
            ).manual_seed(
                current_seed
            )

            result_image = generate_image(
                pipe=pipe,
                prompt=prompt,
                width=width,
                height=height,
                steps=num_inference_steps,
                generator=generator,
            )

            save_image(
                result_image,
                output_path,
            )

            success_count += 1

            print(
                "  Done."
            )

        except KeyboardInterrupt:

            print()
            print(
                "Interrupted by user."
            )

            raise

        except Exception as e:

            print(
                f"  ERROR: {e}"
            )

        print()

    print(
        f"Done. Generated "
        f"{success_count}/{num_images} "
        f"image(s)."
    )

    if success_count != num_images:
        sys.exit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print()
        print("Stopped.")

    except Exception as e:
        print()
        print(
            f"ERROR: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

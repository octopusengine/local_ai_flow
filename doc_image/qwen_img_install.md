Qwen-Image-2.1 — instalace na Mac Studio M5 Max
Archiv instalačního a konfiguračního postupu.

Hardware
Mac Studio

Apple M5 Max

18 CPU cores

36 GB unified memory

macOS

Apple Silicon / MPS

Model:

Qwen-Image-2.1

Hugging Face: Qwen/Qwen-Image-2.1

Lokální umístění modelu:

~/ai/models/Qwen-Image-2.1

Projekt:

~/ai/qwen-image

1. Python
Původní systémový Python byl:

Python 3.9.6

Aktuální diffusers vyžaduje Python >= 3.10, proto byl použit Homebrew Python 3.12.

Instalace:

brew install python@3.12

Kontrola:

/opt/homebrew/bin/python3.12 --version

2. Virtuální prostředí
Vytvoření projektu:

mkdir -p ~/ai/qwen-image
cd ~/ai/qwen-image

Vytvoření virtuálního prostředí:

/opt/homebrew/bin/python3.12 -m venv .venv

Aktivace:

source .venv/bin/activate

Kontrola:

python --version

Výsledkem má být Python 3.12.x.

Při změně prostředí lze původní .venv odstranit:

deactivate 2>/dev/null
rm -rf .venv

3. Základní Python balíčky
Instalace:

python -m pip install -U pip

pip install "torch>=2.4.0"
pip install "transformers>=5.17"
pip install git+https://github.com/huggingface/diffusers
pip install accelerate pillow

Výsledná použitá verze:

PyTorch: 2.14.1
diffusers: 0.41.0.dev0
huggingface_hub: 1.33.0
Python: 3.12.x

4. Ověření Apple MPS
Apple Silicon nepoužívá CUDA. Pro akceleraci se používá MPS.

Test:

python -c "import torch; print('PyTorch:', torch.__version__); print('MPS:', torch.backends.mps.is_available()); print('MPS built:', torch.backends.mps.is_built())"

Očekávaný výsledek:

PyTorch: 2.14.1
MPS: True
MPS built: True

5. Problém s Hugging Face Xet
První pokus o stažení modelu přes from_pretrained() používal Xet a skončil chybou:

RuntimeError: Task error: File reconstruction error:
CAS Client Error: Request middleware error

Proto bylo Xet vypnuto:

export HF_HUB_DISABLE_XET=1

6. Timeouty Hugging Face
Při klasickém HTTP downloadu se objevovaly timeouty:

The read operation timed out

a občas:

[Errno 8] nodename nor servname provided, or not known

Byly nastaveny delší timeouty:

export HF_HUB_DOWNLOAD_TIMEOUT=120
export HF_HUB_ETAG_TIMEOUT=120

Tyto proměnné je vhodné nastavit před downloadem.

7. Verze huggingface_hub
Při pokusu aktualizovat huggingface_hub na 2.0.0 vznikl konflikt:

diffusers 0.41.0.dev0 requires huggingface-hub<2.0,>=1.32.0

Proto byla verze vrácena:

pip install "huggingface_hub>=1.32.0,<2.0"

Výsledná verze:

huggingface_hub: 1.33.0

Kontrola:

hf --version
python -c "import huggingface_hub, diffusers; print('huggingface_hub:', huggingface_hub.__version__); print('diffusers:', diffusers.__version__)"

8. Stažení modelu
Model byl nakonec stažen samostatně pomocí Hugging Face CLI místo přímého downloadu z from_pretrained():

export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=120
export HF_HUB_ETAG_TIMEOUT=120

hf download Qwen/Qwen-Image-2.1 \
  --local-dir ~/ai/models/Qwen-Image-2.1

Download byl několikrát přerušován timeouty, ale příkaz podporoval pokračování z již stažených dat.

Výsledný model zabral přibližně:

31 GB

Kontrola:

du -sh ~/ai/models/Qwen-Image-2.1

9. Kontrola struktury modelu
Model obsahuje mimo jiné:

~/ai/models/Qwen-Image-2.1/
├── LICENSE
├── README.md
├── model_index.json
├── transformer/
├── text_encoder/
├── processor/
├── scheduler/
├── vae/
└── assets/

Transformer:

transformer/
├── config.json
├── diffusion_pytorch_model-00001-of-00002.safetensors
├── diffusion_pytorch_model-00002-of-00002.safetensors
└── diffusion_pytorch_model.safetensors.index.json

Text encoder:

text_encoder/
├── config.json
├── generation_config.json
├── model-00001-of-00004.safetensors
├── model-00002-of-00004.safetensors
├── model-00003-of-00004.safetensors
├── model-00004-of-00004.safetensors
└── model.safetensors.index.json

VAE:

vae/
├── config.json
└── diffusion_pytorch_model.safetensors

10. Chybějící torchvision
Při prvním lokálním načtení modelu se objevila chyba:

ImportError:
Qwen3VLVideoProcessor requires the Torchvision library

Řešení:

pip install -U torchvision

Po instalaci už pipeline prošla inicializací.

11. Finální test.py
Model je načítán z lokálního adresáře, takže po kompletním downloadu není potřeba další přístup k Hugging Face.

import torch
from diffusers import QwenImage21Pipeline

MODEL = "/Users/yenda/ai/models/Qwen-Image-2.1"

print("Loading Qwen-Image-2.1...")
print("PyTorch:", torch.__version__)
print("MPS:", torch.backends.mps.is_available())

pipe = QwenImage21Pipeline.from_pretrained(
    MODEL,
    dtype=torch.bfloat16,
)

pipe = pipe.to("mps")

print("Model loaded.")

prompt = (
    "A cinematic photograph of a futuristic city at night, "
    "rainy streets reflecting neon lights, highly detailed, "
    "realistic photography, dramatic lighting"
)

print("Generating...")

image = pipe(
    prompt=prompt,
    width=1024,
    height=1024,
    num_inference_steps=30,
).images[0]

image.save("output.png")

print("Saved: output.png")

Spuštění:

cd ~/ai/qwen-image
source .venv/bin/activate
python test.py

Výstup:

output.png

12. Poznámky k paměti
Mac má:

36 GB unified memory

Lokální model zabírá přibližně:

31 GB

Proto je konfigurace poměrně těsná. Model byl úspěšně načten a obrázek byl vygenerován na MPS, takže základní konfigurace funguje.

Pokud by při dalších experimentech došlo k:

MPS backend out of memory

nebo výraznému swapování, je vhodné přejít na CPU/MPS offload místo prostého:

pipe.to("mps")

Pro první úspěšný test ale přímé použití MPS fungovalo.

13. Užitečné příkazy
Aktivace prostředí:

cd ~/ai/qwen-image
source .venv/bin/activate

Deaktivace:

deactivate

Kontrola PyTorch/MPS:

python -c "import torch; print(torch.__version__); print(torch.backends.mps.is_available())"

Kontrola velikosti modelu:

du -sh ~/ai/models/Qwen-Image-2.1

Kontrola souborů:

find ~/ai/models/Qwen-Image-2.1 -maxdepth 2 -type f

Generování:

python test.py

Výsledný stav
Instalace byla úspěšně dokončena na:

Mac Studio
Apple M5 Max
36 GB unified memory
Python 3.12
PyTorch 2.14.1
MPS: True
diffusers 0.41.0.dev0
huggingface_hub 1.33.0
Qwen-Image-2.1

Model je lokálně uložen v:

/Users/yenda/ai/models/Qwen-Image-2.1

a první obrázek byl úspěšně vygenerován přes Apple MPS.
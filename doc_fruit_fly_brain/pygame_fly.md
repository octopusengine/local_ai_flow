# Fly + fixed connectome

`Motion (brain drives body)` is a checkbox: checked enables brain-driven movement,
unchecked measures brain outputs without applying them to the body. Its startup
value is `motion_enabled` in `pygame_fly_motor.json`, default **true**. The motor
file holds this switch, `adapter_gain`, `forward` and `turn`. Changes in the UI
apply to the running experiment; edit the file and restart for a persistent default.
Older references below to Motion ON/OFF mean this checked/unchecked state.

Run from `D:\data_codex\fruit_fly_brain`:

```powershell
.\venv\Scripts\python.exe pygame_fly.py
# Start with the smallest experimental network:
.\venv\Scripts\python.exe pygame_fly.py --size twentieth
```

The window starts at 1360 × 790 and can be resized. The complete logical layout
is scaled to fit, without cropping controls. Loading happens in a background
process. The simulation starts paused. `Run` / Space starts repeated steps;
`Step` / Enter computes 50 ms of simulated brain time. The brain keeps membrane
and synaptic state between steps. `Reset state`, changing network size, or
changing connection mode creates a fresh brain and the same seeded world.
Image settings and adapter gain are retained. There is **no learning**.

## Network sizes

| Option | Neurons | Directed connection rows | Selection |
|---|---:|---:|---|
| Full | 138,639 | 15,091,983 | Original model graph |
| Reduced 1/5 | 30,583 | 722,762 | Every fifth internal neuron; all experimental inputs and readouts protected |
| Reduced 1/20 | 6,932 | 35,567 | Every twentieth neuron overall; strongest mapped sugar input protected |

Selection uses ascending root-ID order and is deterministic. The 1/5 option is
slightly larger than an exact fifth because its interface is protected. In the
current dataset the protected sugar neuron already belongs to the 1/20 sample.
Only original edges with both endpoints retained survive. Their signed weights
and delays are unchanged; there is no rewiring, weight multiplication, or
substitution for missing multi-neuron paths. Reduced graphs are ablation
experiments, **not validated smaller equivalents of the full brain**.

A local three-step timing assay measured subsequent 50 ms windows at about
4.49–5.57 seconds (Full), 0.39–0.42 seconds (1/5), and 0.18–0.22 seconds (1/20).
Loading and the first step add overhead. These are short-run timings, not a
performance guarantee. Results: `results/fly/size_verification/`.

## Inputs and outputs actually available

The downloaded Shiu model has 138,639 neurons at FlyWire materialization 783.
The pinned annotation release v2.1.0 matches all of those IDs. Within this model,
16,351 neurons are sensory: 10,855 visual, 2,279 olfactory, 343 gustatory,
2,636 mechanosensory, 74 hygrosensory, 29 thermosensory, 133 unknown sensory,
and 2 unclassified. Another 2,317 are ascending neurons.

This experiment stimulates a selected interface, not all sensory neurons:

| Selected group | Full and 1/5 | 1/20 |
|---|---:|---:|
| Left eye, R1–6 | 1,024 | 58 |
| Right eye, R1–6 | 1,024 | 58 |
| Left / right olfactory | 32 / 32 | 0 / 0 |
| Left / right mechanosensory | 16 / 16 | 0 / 1 |
| Sugar inputs | 20 | 1 |
| Descending left / right / center | 645 / 646 / 8 | 39 / 31 / 1 |
| Head motor readout | 106 | 9 |
| MN9, included in head motor group | 1 | 0 |

The model also includes 76 endocrine neurons, not used as body readouts.
`Absent` means a selected group has no surviving neurons; it is not evidence
that an existing group was physiologically silent. MN9 is absent in 1/20.

Anatomical annotations identify eyes, olfaction, descending neurons and head
motor neurons. They do not directly establish left/right steering. A brain-only
connectome does not supply the complete ventral nerve cord (VNC), leg/wing motor
circuits, muscles or physics. The illustrated six legs share one abstract movement
command; wings are disconnected.

## Pixel stimulation

The master **Vision** checkbox defaults to off (`eye: false`). Enable it for
visual experiments. When off, image projection and scalar eye sampling are
skipped and external visual inputs are zero. Visual neurons remain in the
connectome and may still receive recurrent activity. Per-eye toggles are
subordinate to the master switch.

Each eye uses a 32 × 32 luminance image. `Load L` or `Load R` resizes a file to
32 × 32 for that eye. `Load 64×32` resizes to 64 × 32, then sends columns 0–31 to
the left eye and 32–63 to the right eye. The other eye is unchanged when loading
only one side; use `L enabled` / `R enabled` to disable it explicitly.

One pixel drives one selected R1–6 neuron through a Poisson input. White requests
the slider's frequency (default 150 Hz), black requests zero, and intermediate
brightness scales the frequency linearly. Color is converted to luminance.
`data/fly_annotations/eye_pixels.csv` records the exact pixel-to-root-ID map.
IDs are sorted after seeded selection: **this is not anatomical retinotopy**,
an ommatidial reconstruction, or a validated model of image perception.

In 1/20, 58 pixels per eye remain connected. Removed pixels are shown purple;
they do not stimulate substitute neurons. The input image itself remains 32 × 32.
Preview images show the next requested input. Event counts and output rates
describe the last completed window. A dark eye can still receive recurrent
network activity; its external input-event count is what should be zero.

Example images are in `data/fly_stimuli/`: single-eye bars/checkerboards,
left-only and right-only 64 × 32 images, and a binocular image. `Bars / checker`
generates patterns without a file dialog. `Dark` disables visual stimulation.

## Body and environment

The world has 30 × 30 cells. The purple circle is the abstract fly and orange
dots are sugar. The `World` vision mode projects artificial floor texture and
walls into the eyes; **it does not render sugar or the odor overlay**. Sugar now
emits an artificial odor. The two olfactory input groups sample the immediately
adjacent left and right cells relative to body heading, rather than the occupied
cell. Heading is rounded to the same cardinal direction as grid movement; outside
the world the sample is zero. The configurable
`sugar_odor_radius` is 1, 2 (default), or 3 grid cells, giving square areas of
3×3, 5×5 or 7×7. Chebyshev distance 0/1 gives 100%, distance 2 gives 50%, and
distance 3 gives 25%; outside the radius the signal is zero. Overlapping sources
use the strongest signal rather than adding. A consumed source disappears
immediately; the held sugar-contact signal remains a separate input.

The map shows an observer-only yellow tint at 18%, 9% or 4.5% opacity according
to odor strength. This tint never enters visual stimuli. The `World odor L/R`
label shows the current environmental signal. Checkboxes `Left odor enabled`
and `Right odor enabled` default to checked (`left_odor: true`, `right_odor: true`).
Checked passes environmental intensity; unchecked sends zero to that side.
These replace the former forced 100% probes. Set `sugar_odor_enabled` to false
and restart for isolated visual/contact experiments. The initial
darkness baseline also needs this setting for guaranteed absence of odor.

This is an experimental mapping of sugar proximity onto selected olfactory
neurons, not a validated chemical/receptor model. It adds a proximity signal,
with a body-relative left/right directional difference. Reduced 1/20 still has no surviving
selected olfactory inputs, so its smell cannot drive the neural model.

The fly and its body diagram turn green immediately when sugar is under the
fly and remain green while the current contact signal is held. They return to
purple when it ends. Pausing also pauses this countdown. Green indicates sensory
contact, not a measured neural output response.

Sugar becomes an input only on contact. On collection the contact signal is
held for the current and next three 50 ms windows (200 ms total). `Place sugar
under fly` provides a reproducible contact test. In pause, arrow keys manually
move the body; those movements are not caused by the brain. `Motion OFF / assay`
lets the brain run without applying its motor commands to the body.

External movement is available with keyboard arrows or the on-screen L / R /
T / D buttons. One press translates the body one grid cell without changing its
heading, pauses automatic stepping and switches vision to World. Eye previews
update immediately; disabled eyes remain disabled. Press Enter to send the new
view to the brain. Use Motion OFF for exclusively manual movement. If a brain
step is in progress, wait for it to finish and press the arrow again. Wall
collisions produce a touch input; external moves are logged as `manual_move`.

Let L and R be mean descending-neuron firing rates on the annotated sides.
The same experimental adapter computes forward = clip(gain × (L+R)/2, 0, 1)
and turn = clip(gain × (R−L) × 30, −45, 45) degrees per window. Forward credit
accumulates until a grid step is possible. Default gain is 8. These are arbitrary
control rules, not measured gait equations. Head motor and MN9 activity are
displayed but do not control grid movement. No hidden random exploration is added;
the fly can therefore remain stationary.

## Editable motor matrix

`pygame_fly_motor.json`, selected by `motor_matrix_file` in the main settings,
contains `adapter_gain` (default 8.0) and two rows: `forward` and `turn`. Each has weights for `dn_left`,
`dn_right`, `dn_center`, `head_motor`, and `mn9`. Output × weight is summed and
multiplied by adapter gain, then clipped to 0..1 (forward) or −45..45 degrees
(turn). The shipped matrix preserves the previous formulas. Positive turn is
clockwise on screen, negative is counterclockwise. This changes our controller,
not the connectome's synaptic weights. Restart after editing. Resolved weights
are saved in logs and session settings; workers inherit that snapshot.
`adapter_gain` belongs in this motor file, not the main settings file. The UI
gain slider overrides it for the current experiment without rewriting the file.

Try all turn weights zero to disable turning, −3/+3 instead of −30/+30 to weaken
it tenfold, or opposite signs to reverse steering. Balancing unequal baseline
activity requires `wL × mean(L) + wR × mean(R)` near zero, then independent trials.
This is manual calibration, not learning. The body log includes unclipped
`raw_forward` and `raw_turn_degrees` to identify saturation. MN9 is also included
in `head_motor`; weighting both readouts counts its contribution twice.

## The strongest sugar input

Among the 20 mapped sugar inputs, root ID **720575940639198653** has both the
largest summed absolute outgoing weight (719) and strongest single edge (91),
with 93 distinct targets in the full original graph. These values are in the
source connectivity units; the model multiplies them by 0.275 mV. They are
structural weights, not measured sensitivity or proof of strongest behavioral
effect. The ranking is saved in `data/fly_annotations/sugar_input_weights.csv`.

That neuron is protected in 1/20. Only four of its original target neurons
survive there, with weights totaling 7. Preserving this input alone does not
preserve its downstream response. MN9 is still absent: rescuing entire paths
would be a different reduction experiment.

## Suggested experiments

1. **Left versus right image:** select Full or 1/5, disable motion, choose Dark,
   reset, and take two baseline steps. Load `left_only_64x32.png` and step several
   times. Record outputs. Reset and repeat with `right_only_64x32.png`, using the
   same strength and number of steps. Do not compare unequal histories.
2. **Spatial pattern versus brightness:** compare bars and checkerboards with
   equal mean luminance, resetting between trials. A different response would
   demonstrate sensitivity to this experimental pixel assignment, not natural
   image recognition. Direct-sensor mode uses mean brightness only.
3. **Reduction:** repeat the same dark/left/right sequence with Full, 1/5 and 1/20.
   Inspect missing groups, active neurons, outputs and runtime. There is no weight
   compensation: lower activity or lost behavior is an expected possible result.
4. **Sugar contact:** in Full, turn vision dark and motion off, reset, take baseline
   steps, then place sugar under the fly and take 6–8 steps. Observe the input
   pulse and MN9. Repeat in 1/5. In 1/20 inspect descending/head motor readouts;
   MN9 cannot respond because it was removed.
5. **Connection control:** compare Real connections against Shuffled targets at
   the same size, stimulus, seed, strength and adapter gain. Shuffling permutes
   retained target endpoints, preserving in/out degree counts and source weights,
   but can introduce self-loops and parallel edges. Direct sensors bypasses the
   brain through a handwritten rule; its displayed values are adapter units,
   not Hz, and are not directly numerically comparable with firing rates.

Pearson correlations use up to 300 completed windows, with input followed by
output one window (50 ms) later. Constant signals are omitted. The display shows
the largest absolute correlations, which is exploratory and selection-biased.
Correlation does not establish causation; repeated controlled trials and
targeted interventions are needed before interpreting biological function.

## Logs, comparisons and checks

`pygame_fly.json` is read at startup:

```json
{
  "log": true,
  "window_height": 790,
  "screenshot_every_steps": 50
}
```

The example above shows only the logging/display subset; omitted keys use
defaults. The actual configuration file also contains these experiment settings:

| Setting | Default | Meaning / allowed values |
|---|---|---|
| `network_size` | `full` | `full`, `fifth`, `twentieth`; `--size` overrides it |
| `connection_mode` | `real` | `real`, `shuffled`, `direct` |
| `brain_seed` | 42 | Poisson noise seed; shuffling uses this seed + 100 |
| `world_seed` | 31 | Reproducible sugar placement sequence |
| `stimulus_hz` | 150 | White-pixel / maximum sensor drive, 0–300 Hz |
| `adapter_gain` (in the motor file) | 8 | Experimental movement gain, 1–32 |
| `motor_matrix_file` | `./pygame_fly_motor.json` in the supplied file | Editable motor readout matrix |
| `eye` | false | Master vision enable; skips image calculation when off |
| `left_odor`, `right_odor` | true | Enable each environmental olfactory input |
| `vision_mode` | `world` | `world`, `image` (initial bars), `dark` |
| `motion_enabled` (in the motor file) | true | Initial Motion checkbox state; false for stationary assays |
| `food_count` | 24 | World sugar count, 1–899; manual placement may add extra sugar |
| `sugar_odor_enabled` | true | Enable environmental sugar odor; false isolates other stimuli |
| `sugar_odor_radius` | 2 | Square odor radius in grid cells: 1, 2, or 3 |
| `contact_windows` | 4 | Sugar-contact duration including the first window; each is 50 ms |
| `benchmark_world_steps` | 12 | Length of each comparison's closed-loop trial |
| `window_width` | 1360 | Initial width; the layout scales with the window |
| `data_dir` | `./data` | Contains `fly_annotations/` and `fly_stimuli/` |
| `model_data_dir` | `./external/Drosophila_brain_model` | Contains `Completeness_783.csv` and `Connectivity_783.parquet` |
| `results_dir` | `./results` | Sessions and benchmarks go in its `fly/` subdirectory |
| `log_dir` | `./log` | Text logs and PNG snapshots |

Relative paths are resolved against the directory containing `pygame_fly.py`,
not the terminal working directory. Absolute paths are supported; use JSON paths
such as `"D:/fly_data"` (or escape backslashes). Changing a path does not move or
download files. Keep annotations, interface IDs and model files consistent with
FlyWire 783. `model_data_dir` selects data files only; the Python dynamics code
still comes from the existing `external/Drosophila_brain_model` installation.
The existing `.runtime` cache configuration is unchanged and stays on D:.

Each new run begins with a **`configuration` log record** containing all effective
settings, including defaults, CLI size overrides and resolved absolute paths.
A second run in the same minute appends its own configuration record before its
events. Each experiment also saves `settings.json` beside its detailed telemetry.
Child workers receive this settings snapshot, so editing the JSON while a run is
active cannot silently change its data paths or seed. UI controls change current
values and are logged; they do not rewrite the configuration file. Reset uses the
configured world seed and preserves current interactive stimulus/adapter controls.

The comparison uses current strength, gain, master vision, odor enables and the
motor matrix plus configured seeds and food settings. Its predefined assay
replaces GUI images/per-eye toggles and runs the motor controller, even if interactive
motion was disabled. It records its launch settings in `benchmark_ui/settings.json`.
Unknown keys and invalid types/ranges produce an error rather than silently
ignoring a misspelled parameter. Start paused remains fixed; the 50 ms window,
pixel mapping and biological model weights are not adjustable via this file.

With `log: true`, a readable UTF-8 JSON record per line is appended to
`log/YYMMDD_HHMM_log.txt` (local date/time, two-digit year). It includes application
and experiment starts, network configuration, stimulus summaries, measured inputs
and outputs, timings, image hashes, body movement, control changes and errors.
Starts within the same minute append to the same file, each with a new start
record. Full pixel requests remain in the detailed session telemetry below.

PNG snapshots of the displayed canvas are saved on brain readiness, after the
first and every 50th completed step, when paused, and on close. Press **F12** for
a manual snapshot. Names include the size selector (`full`, `05`, `20`), connection
mode and event, for example `260918_1430_20_real_step000050.png`. Repeated names
receive a numbered suffix and never overwrite earlier snapshots. Images use the
current window dimensions. The interval is configurable; snapshots are not taken
every display frame. Restart the application after editing settings.

`log: false` disables this additional text/PNG log. Existing detailed session
telemetry and worker diagnostics below remain available. All paths are relative
to the project on D:, independent of the shell's current directory.

Sessions write to `results/fly/sessions/`: mapping, network configuration, worker
log, and JSONL telemetry with full requested pixel arrays, stimulus strength,
responses, image hashes, body position and actual adapter settings. Configuration
records retained-ID hash, sizes, seed, surviving eye-pixel indices and group counts.
Old result folders may describe earlier interfaces; inspect their metadata.

`Compare 3 modes` runs a paired probe protocol and short seeded closed-loop assay
for the currently selected size. It stops the interactive worker and stores results
in `results/fly/benchmark_ui/` (overwritten by the next comparison). Afterward use
Reset state to restart the interactive brain. The probe protocol uses uniform
channel intensities, not spatial images. The short world assay uses scalar wall/
texture brightness, rather than the GUI's image projection.

```powershell
.\venv\Scripts\python.exe fly_experiment.py --size twentieth --output results/fly/benchmark_20
.\venv\Scripts\python.exe -m unittest test_fly -v
.\venv\Scripts\python.exe verify_fly_sizes.py
```

The earlier Full comparison in `results/fly/benchmark_pixels_v2/` verified matching
external Poisson events for real versus shuffled probe runs. Peak MN9 was 100 Hz
for real and 0 Hz for shuffled, across the whole probe protocol. Both brain-driven
short world trials made zero moves; direct mode made five. This is one seed and
an untuned adapter, **not evidence of learned navigation or a useful behavioral
advantage**. The code keeps original source data and weights unchanged. Runtime
files and results remain on D: through the project's existing runtime setup.

## Sources

- [Pinned FlyWire annotations v2.1.0](https://github.com/flyconnectome/flywire_annotations/tree/v2.1.0)
- [Shiu et al., whole-brain computational model](https://www.nature.com/articles/s41586-024-07763-9)
- [FlyWire cell-type annotation paper](https://www.nature.com/articles/s41586-024-07686-5)
- [Descending and ascending brain–VNC connectivity](https://www.nature.com/articles/s41586-025-08925-z)

Counts above were computed from the intersection of the local model and pinned
annotations, not copied from a paper's potentially different dataset subset.

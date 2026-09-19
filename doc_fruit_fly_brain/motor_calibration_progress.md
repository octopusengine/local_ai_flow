# Motor calibration checkpoint — 2026-09-18

## Objective and constraints

Improve movement toward sugar in the `fifth` network without online learning or
changing synaptic weights. The user requested body-relative neighboring-cell
olfactory sampling, and then inspecting individual neurons rather than relying
only on anatomical left/right group means.

## Implemented in the working files

- Left/right odor now samples the adjacent cell on each side of the body,
  rotated with its cardinal heading. Outside-world samples are zero.
- The GUI displays both neighboring odor intensities.
- Motor matrices now accept additional `neuron_<18-digit root ID>` columns in
  both `forward` and `turn`, in addition to the five existing aggregate outputs.
- `Brain` can report those individual neurons in Hz. Missing reduced neurons
  have zero output and are marked absent; choosing readouts does not protect
  extra neurons or change graph selection. Direct bypass mode has no individual
  neural readouts and returns zero for those columns.
- Selected readouts are displayed in the right-hand panel and recorded in logs.
- The shipped `pygame_fly_motor.json` still holds the original matrix. No new
  candidate has been adopted as the default yet.

## Measurements completed

Baseline, world seed 31, brain seed 42, 40 steps: 0 foods, 39 moves, 8 unique
cells, 39 turns clipped at the −45 degree limit. Simply increasing global gain
would worsen saturation. World seed 32 has no initial odor, and the unforced
network does not start moving; this is a separate exploration limitation.

Gentle aggregate rebalancing removed clipping and expanded visited cells, but
did not collect sugar in the tested short runs. Slower forward drive helped:
`slow_left` collected one sugar on each of seeds 31 and 33 in 40 steps, but
still showed a persistent turning bias. This is not proof of gradient following.

An aggregate/head-motor readout (`odor_head_readout`) collected one sugar on
each of seeds 31 and 33 in 80 steps without clipping. Its forward weights were
0.01/0.01 and turn weights dn_left=1, head_motor=-20, at gain 8. This is a
candidate, not an adopted or broadly validated controller.

## Individual neuron scan

`scan_fly_motor_neurons.py` measured all 1,299 descending and 106 head-motor
neurons in the fifth network under quiet, left, right and bilateral odor.
Seeds 42 and 43; 20 windows per condition; last 12 windows averaged after an
8-window warm-up. No weight updates. Complete data and ranking are saved in
`results/fly/motor_neuron_scan/scan.json` and `ranking.csv`.

Two selected candidates:

| Root ID | Label | Left-only Hz (42 / 43) | Right-only Hz (42 / 43) |
|---|---|---|---|
| 720575940612603289 | DNg75, anatomical right | 8.33 / 6.67 | 0 / 1.67 |
| 720575940629461442 | descending, anatomical right, no cell type label | 0 / 0 | 13.33 / 11.67 |

Both were silent in the quiet condition. The left-preferring candidate also
responded to bilateral odor (5 Hz), whereas the right-preferring candidate did
not. Thus they are not symmetric left/right detectors. They are empirical model
readouts, not verified biological steering neurons. Selection from many neurons
needs independent confirmation; seed 43 already participated in selection.

## Reproducible scripts and result folders

- `calibrate_fly_motor.py`: fixed-matrix closed-loop trials; restores initial
  brain state and random seed between runs. Supports explicit candidates,
  world seeds, brain seed and step count. Vision is intentionally disabled.
- `probe_fly_odor.py`: aggregate odor responses.
- `scan_fly_motor_neurons.py`: per-neuron candidate scan.
- `verify_fly_readouts.py`: independent seed 44 probes, verifies individual
  readout values against spike counts and checks unchanged synaptic weights.
- `results/fly/motor_calibration_baseline`: old central-odor baseline.
- `results/fly/motor_calibration_directional`: neighboring-cell baseline and
  gentle/straight controls, 40 steps.
- `results/fly/motor_calibration_slow`: four slower aggregate candidates.
- `results/fly/motor_calibration_decoder`: aggregate directional candidates.
- `results/fly/motor_calibration_crawl`: 80-step very slow aggregate candidate.
- `results/fly/motor_calibration_head`: 80-step aggregate/head candidate.
- `results/fly/motor_calibration_neurons`: individual-readout trials.

## In progress at checkpoint

`verify_fly_readouts.py` and the individual-readout closed-loop trial were
launched, along with unit tests. Inspect their resulting files before rerunning.
The first individual-only candidate (`pair_drive`) collected 0 sugar on seed 31
and 1 on seed 33 in 80 steps; it retained a negative turning bias. The alternative
`pair_group_drive` was still being evaluated when this note was written.

## Next steps

### Results received while saving the checkpoint

All launched jobs have now finished. The 14 unit tests passed. Independent
seed 44 preserved the response preference: the left candidate averaged 3.33 Hz
for left-only versus 1.67 Hz for right-only; the right candidate averaged 0 Hz
for left-only versus 53.33 Hz for right-only. The large right-response change
relative to seeds 42/43 shows substantial gain variability. Exact individual
readout checks and the unchanged-synaptic-weight check passed.

`pair_group_drive` collected 0 sugars on world 31 and 1 on world 33 in 80 steps.
On world 33 it had 60 clipped turns and a total +2546.4 degrees of rotation.
Thus the individual-neuron matrix is not ready to replace the default: selectivity
in a static probe did not yield robust closed-loop steering. No jobs remain
running at this checkpoint. The aggregate/head candidate remains the most
promising measured compromise, but additional matched baseline/holdout trials
are still needed before a confident recommendation.

1. Inspect `heldout_seed44.json` and the final individual-trial summary.
2. Compare a selected candidate and baseline for the same number of steps on
   additional odor-present worlds and a new brain seed. Keep no-odor cases
   separate rather than hiding them in an average.
3. Choose a demonstrably useful conservative default, or report that no robust
   directional controller has yet been identified. Save the old motor JSON
   before adopting a candidate.
4. Update the English/Czech docs with individual-readout syntax and the actual
   measured limits. Recheck custom readouts with Motion off and reduced networks.

The general documentation currently describes the new neighboring-cell odor
sampling; the new individual-readout feature is not yet fully documented there.
This checkpoint is intentionally an intermediate record, not a completion claim.

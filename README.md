# scowl
Managing smart-grid resources with a distributed SCADA implemented with OWL

# System Overview

Scowl is built out of three (3) core entities. In the real world, each entity would reside on a discrete host connected over the Internet. For the purposes of evaluation, each `Tracker` has its own host, which it shares with the `Peers` and `SuperPeers` it is responsible for.

## Tracker
Equivalent to a `region`al grid controller. Holds region state including total generation and demand. Computes *ephemeral distribution trees* for each `generator`, fitting as many `consumer`s within its tree as is safe to do.

## Peer
Equivalent to a Distributed Energy Resource (DER). May be one of `generator` or `consumer`.

## Super-Peer
A special peer that can `transition()` between being a `consumer` and `generator` (i.e., storage, like batteries or cars). Once a `super-peer` has transitioned to being a generator, it has a fixed `capacity` (measured in kWh) that it can give back to the grid. After depleting its `capacity` it goes into `sleep_mode`, where it is neither consuming nor generating. In `sleep_mode` it advertises that it wants to consume at its `charging rate` but is intentionally starved until its `region` has spare capacity, not reserved for *stochastic consumption* but regular `peer`s.

# Generators
a `Generator` comes in one of three (3) types:
    - stochastic
    - fixed
    - continuous

**Stochastic Generators** generate *randomly* up to a `MaxCapacity`, as determined by external factors (e.g., weather).

**Fixed Generators** generate at 100% of `MaxCapacity` constant rate when online.

**Continous Generators** may generate from 0% to 100% of their `MaxCapacity`, as determined by their `tracker`.

All generators know how much `DemandResponsiveConsumption` the `Consumer`s in their tree have. A tree has a `MaxDemandResponsiveConsumption`. Issuing a `shed()` signal to `Consumer`s is a last resort. It is issued **only** after a `Tracker` cannot balance its region by asking `Storage` to `StopStoring()`/`Transition()` to `Generator`-mode, or bringing new `Fixed Generators` online.

# Consumers
a `Consumer` may have a mix of consumption proportions. It may have a % of its `MaxConsumption` up to which its consumption may be *stochastic*. It may have a % of its `MaxConsumption` that is `defer`rable up to a fixed %. `MaxConsumption` = `StochasticConsumption` + `DeferrableConsumption`. `Consumer`s may have a % of their `DeferrableConsumption` that is *demand responsive*, meaning a `Generator`s can issue an RPC to have the `Consumer` `shed()` a fixed amount of consumption. The consumer `ACK`s that it can/will shed the load (the `DemandResponsiveConsumption`).

# Storage 
Storage (Super-Peers), must respond to `StartStoring()` and `StopStoring()` RPCs from the generator in their distribution tree. Storage DERs switch from `Consumer`s to `Generator`s upon receiving `

# Trackers
Trackers compute *ephemeral distribution trees* for temporary groups of `Generator`s and `Consumer`s within its region. Trackers match `Consumer`s with `Generator`s such that the maximum amount of available generation is being utilized and the number of *starving* consumers is minimized.

export type ApiSession = {
  meeting_name: string;
  session_name: string;
  session_status: string;
  current_lap: number;
  total_laps: number;
  track_temperature: number;
  air_temperature: number;
  rainfall: boolean;
  race_control_status: string;
};

export type ApiDriver = {
  driver_number: number;
  name: string;
  acronym: string;
  team_name: string;
  team_colour: string;
  position: number;
  current_lap: number;
  x: number | null;
  y: number | null;
  compound: string;
  tyre_age: number;
  last_lap_time: number;
  gap_to_leader: number;
  interval_ahead: number | null;
  interval_behind: number | null;
  pit_stops: number;
};

export type ApiCompoundProbabilities = {
  SOFT: number;
  MEDIUM: number;
  HARD: number;
  INTERMEDIATE: number;
  WET: number;
};

export type ApiPrediction = {
  driver_number: number;
  pit_within_3_laps: number;
  pit_within_5_laps: number;
  pit_within_7_laps: number;
  predicted_next_compound: string;
  compound_probabilities: ApiCompoundProbabilities | null;
  updated_at: string;
};

export type RaceState = {
  session: ApiSession;
  drivers: ApiDriver[];
  predictions: ApiPrediction[];
};

export type TrackPoint = { x: number; y: number };
export type TrackState = {
  circuit_name: string;
  circuit_key: number;
  rotation: number;
  country_name?: string;
  start_finish: TrackPoint;
  path: TrackPoint[];
  pit_lane?: TrackPoint[];
};

// Player Types
export interface PlayerResponse {
    id: number;
    name: string;
    registered_at: string;
}

export interface CreatePlayerRequest {
    name: string;
}

export interface EditPlayerRequest {
    name?: string | null;
}

export interface PlayersPairResponse {
    player1: PlayerResponse;
    player2: PlayerResponse;
}

// Tour Types
export interface TourResponse {
    id: number;
    name: string;
    started_at: string;
    ended_at: string | null;
}

export interface CreateTourRequest {
    name: string;
    started_at?: string | null;
    ended_at?: string | null;
}

export interface EditTourRequest {
    name?: string | null;
    started_at?: string | null;
    ended_at?: string | null;
}

export interface TourPlayerPointsResponse {
    player: PlayerResponse;
    player_tour_points: number;
}

export interface TourPlayersPairProposeResponse {
    players_pair: PlayersPairResponse;
    last_played_at: string | null;
}

// Match Types
export interface MatchResponse {
    id: number;
    played_at: string;
    players_pair1: PlayersPairResponse;
    players_pair2: PlayersPairResponse;
    players_pair1_score: number;
    players_pair2_score: number;
}

export interface RegisterMatchNetSideRequest {
    player1_id: number;
    player2_id: number;
    match_score: number;
}

export interface RegisterMatchRequest {
    side1: RegisterMatchNetSideRequest;
    side2: RegisterMatchNetSideRequest;
    played_at?: string | null;
}

// Validation Types
export interface ValidationError {
    loc: (string | number)[];
    msg: string;
    type: string;
    input?: any;
    ctx?: Record<string, any>;
}

export interface HTTPValidationError {
    detail?: ValidationError[];
}

// Player Types
export interface PlayerResponse {
    id: number;
    name: string;
    registered_at: string;
}

export interface CreatePlayerRequest {
    name: string;
    registered_at?: string | null;
}

// Tour Types
export interface TourResponse {
    id: number;
    name: string;
    started_at: string;
    ended_at: string | null;
}

export interface StartTourRequest {
    name: string;
    started_at?: string | null;
    ended_at?: string | null;
}

export interface EndTourRequest {
    ended_at: string;
}

export interface TourPlayerPointsResponse {
    player: PlayerResponse;
    player_tour_points: number;
}

// Match Types
export interface PlayersPairResponse {
    player1: PlayerResponse;
    player2: PlayerResponse;
}

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
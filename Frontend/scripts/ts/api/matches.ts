import { apiClient } from './client.js';
import { MatchResponse, RegisterMatchRequest } from '../types/index.js';

export const matchesApi = {
    async getAll(playerId?: number, playedAfter?: string, playedBefore?: string): Promise<MatchResponse[]> {
        const params = new URLSearchParams();
        if (playerId) params.append('player_id', playerId.toString());
        if (playedAfter) params.append('played_after', playedAfter);
        if (playedBefore) params.append('played_before', playedBefore);
        const query = params.toString();
        return apiClient.get<MatchResponse[]>(`/matches?${query}`);
    },

    async getById(matchId: number): Promise<MatchResponse> {
        return apiClient.get<MatchResponse>(`/matches/${matchId}`);
    },

    async register(data: RegisterMatchRequest): Promise<MatchResponse> {
        return apiClient.post<MatchResponse>('/matches', data);
    },
    
    async delete(matchId: number): Promise<void> {
        return apiClient.delete<void>(`/matches/${matchId}`);
    },
};

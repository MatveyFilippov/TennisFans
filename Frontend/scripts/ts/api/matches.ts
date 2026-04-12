import { apiClient } from './client.js';
import { MatchResponse, RegisterMatchRequest } from '../types/index.js';

export const matchesApi = {
    async getAllForPlayer(playerId: number, startDate?: string, endDate?: string): Promise<MatchResponse[]> {
        const params = new URLSearchParams();
        params.append('player_id', playerId.toString());
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        const query = params.toString();
        return apiClient.get<MatchResponse[]>(`/matches?${query}`);
    },

    async getById(matchId: number): Promise<MatchResponse> {
        return apiClient.get<MatchResponse>(`/matches/${matchId}`);
    },

    async register(data: RegisterMatchRequest): Promise<MatchResponse> {
        return apiClient.post<MatchResponse>('/matches', data);
    },
};
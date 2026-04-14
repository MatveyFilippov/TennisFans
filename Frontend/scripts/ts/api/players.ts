import { apiClient } from './client.js';
import { PlayerResponse, CreatePlayerRequest, EditPlayerRequest } from '../types/index.js';

export const playersApi = {
    async getAll(): Promise<PlayerResponse[]> {
        return apiClient.get<PlayerResponse[]>('/players');
    },

    async getById(playerId: number): Promise<PlayerResponse> {
        return apiClient.get<PlayerResponse>(`/players/${playerId}`);
    },

    async create(data: CreatePlayerRequest): Promise<PlayerResponse> {
        return apiClient.post<PlayerResponse>('/players', data);
    },
    
    async edit(playerId: number, data: EditPlayerRequest): Promise<PlayerResponse> {
        return apiClient.patch<PlayerResponse>(`/players/${playerId}`, data);
    },
    
    async delete(playerId: number): Promise<void> {
        return apiClient.delete<void>(`/players/${playerId}`);
    },
};

import { toursApi } from '../api/tours.js';
export class TournamentBoard {
    constructor(containerId, tourSelectId) {
        this.tours = [];
        this.container = document.getElementById(containerId);
        this.tourSelect = document.getElementById(tourSelectId);
        this.init();
    }
    async init() {
        await this.loadTours();
        this.setupEventListeners();
    }
    async loadTours() {
        try {
            this.tours = await toursApi.getNotEnded();
            if (this.tours.length === 0) {
                this.tours = await toursApi.getAll();
            }
            this.renderTourOptions();
            if (this.tours.length > 0) {
                const latestTour = this.tours.reduce((latest, tour) => tour.id > latest.id ? tour : latest);
                this.tourSelect.value = latestTour.id.toString();
                await this.loadTournamentData(latestTour.id);
            }
            else {
                this.renderEmptyState('Нет доступных туров');
            }
        }
        catch (error) {
            console.error('Failed to load tours:', error);
            this.renderError('Не удалось загрузить список туров');
        }
    }
    renderTourOptions() {
        this.tourSelect.innerHTML = this.tours
            .map(tour => `<option value="${tour.id}">${this.escapeHtml(tour.name)}</option>`)
            .join('');
    }
    setupEventListeners() {
        this.tourSelect.addEventListener('change', async () => {
            const tourId = parseInt(this.tourSelect.value);
            if (tourId) {
                await this.loadTournamentData(tourId);
            }
        });
    }
    async loadTournamentData(tourId) {
        try {
            this.renderLoading();
            const pointsData = await toursApi.getPlayersPoints(tourId);
            this.renderLeaderboard(pointsData);
        }
        catch (error) {
            console.error('Failed to load tournament data:', error);
            this.renderError('Не удалось загрузить данные турнира');
        }
    }
    renderLeaderboard(data) {
        if (data.length === 0) {
            this.renderEmptyState('В этом туре пока нет данных');
            return;
        }
        const sortedData = [...data].sort((a, b) => b.player_tour_points - a.player_tour_points);
        const html = `
            <div class="leaderboard__header">
                <span>Место</span>
                <span>Игрок</span>
                <span>Очки</span>
            </div>
            ${sortedData.map((item, index) => {
            const rankClass = index < 3 ? 'leaderboard__rank--top' : '';
            return `
                    <div class="leaderboard__row">
                        <span class="leaderboard__rank ${rankClass}">${index + 1}</span>
                        <span class="leaderboard__name">${this.escapeHtml(item.player.name)}</span>
                        <span class="leaderboard__points">${item.player_tour_points}</span>
                    </div>
                `;
        }).join('')}
        `;
        this.container.innerHTML = html;
    }
    renderLoading() {
        this.container.innerHTML = '<div class="leaderboard__loading">Загрузка...</div>';
    }
    renderEmptyState(message) {
        this.container.innerHTML = `<div class="leaderboard__loading">${this.escapeHtml(message)}</div>`;
    }
    renderError(message) {
        this.container.innerHTML = `<div class="leaderboard__loading" style="color: #e74c3c;">${this.escapeHtml(message)}</div>`;
    }
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    async refresh() {
        await this.loadTours();
    }
}

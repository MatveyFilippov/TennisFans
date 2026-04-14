import { toursApi } from './api/tours.js';
import { TourResponse, TourPlayersPairProposeResponse, PlayerResponse } from './types/index.js';

class PairsApp {
    private tourSelect: HTMLSelectElement;
    private pairsContainer: HTMLElement;
    private emptyState: HTMLElement;
    private toastContainer: HTMLElement;

    private activeTours: TourResponse[] = [];
    private currentPairs: TourPlayersPairProposeResponse[] = [];

    constructor() {
        this.tourSelect = document.getElementById('tourSelect') as HTMLSelectElement;
        this.pairsContainer = document.getElementById('pairsContainer')!;
        this.emptyState = document.getElementById('emptyState')!;
        this.toastContainer = document.getElementById('toastContainer')!;

        this.init();
    }

    private async init() {
        this.setupEventListeners();
        await this.loadActiveTours();
    }

    private setupEventListeners() {
        this.tourSelect.addEventListener('change', () => this.handleTourChange());
    }

    private async loadActiveTours() {
        try {
            this.renderLoading();

            this.activeTours = await toursApi.getNotEnded();

            if (this.activeTours.length === 0) {
                this.showEmptyState('Нет активных туров');
                this.tourSelect.innerHTML = '<option value="">Нет активных туров</option>';
                return;
            }

            this.renderTourOptions();

            const latestTour = this.activeTours.reduce((latest, tour) =>
                tour.id > latest.id ? tour : latest
            );
            this.tourSelect.value = latestTour.id.toString();

            await this.loadPairs(latestTour.id);
        } catch (error) {
            console.error('Failed to load tours:', error);
            this.showToast('Не удалось загрузить список туров', 'error');
            this.showEmptyState('Ошибка загрузки туров');
        }
    }

    private renderTourOptions() {
        this.tourSelect.innerHTML = this.activeTours
            .map(tour => `<option value="${tour.id}">${this.escapeHtml(tour.name)}</option>`)
            .join('');
    }

    private async handleTourChange() {
        const tourId = parseInt(this.tourSelect.value);
        if (tourId) {
            await this.loadPairs(tourId);
        }
    }

    private async loadPairs(tourId: number) {
        try {
            this.renderLoading();

            this.currentPairs = await toursApi.getProposedPairs(tourId);

            if (this.currentPairs.length === 0) {
                this.showEmptyState('Для этого тура пока нет предложенных пар');
                return;
            }

            this.renderPairs(this.currentPairs);
        } catch (error) {
            console.error('Failed to load pairs:', error);
            this.showToast('Не удалось загрузить предложенные пары', 'error');
            this.showEmptyState('Ошибка загрузки пар');
        }
    }

    private renderPairs(pairs: TourPlayersPairProposeResponse[]) {
        this.emptyState.style.display = 'none';

        const html = pairs.map((pair, index) => this.renderPairCard(pair, index)).join('');
        this.pairsContainer.innerHTML = html;
    }

    private renderPairCard(pair: TourPlayersPairProposeResponse, index: number): string {
        const lastPlayedInfo = !pair.last_played_at ? 'Ранее не играли' : `Играли: ${this.formatRelativeTime(pair.last_played_at)}`;
        
        return `
            <div class="pair-card">
                <div class="pair-card__header">
                    <span class="pair-card__number">Пара #${index + 1}</span>
                    <span class="pair-card__badge">${lastPlayedInfo}</span>
                </div>
                <div class="pair-card__players">
                    ${this.renderPlayerItem(pair.players_pair.player1)}
                    ${this.renderPlayerItem(pair.players_pair.player2)}
                </div>
                <div class="pair-card__footer">
                    <span class="pair-card__avg_points">Усреднённые очки: ${"TODO"}</span>
                </div>
            </div>
        `;
    }

    private renderPlayerItem(player: PlayerResponse): string {
        return `
            <div class="pair-player">
                <div class="pair-player__info">
                    <div class="pair-player__name">${this.escapeHtml(player.name)}</div>
                    <div class="pair-player__id">Место в рейтинге: #${"TODO"}</div>
                </div>
            </div>
        `;
    }
    
    private formatRelativeTime(dateString: string): string {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays < 1) return 'сегодня';
        if (diffDays < 7) return `${diffDays} дн. назад`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} нед. назад`;
        if (diffDays < 365) return `${Math.floor(diffDays / 30)} мес. назад`;
        return `> ${Math.floor(diffDays / 365)} г. назад`;
    }

    private renderLoading() {
        this.emptyState.style.display = 'none';
        this.pairsContainer.innerHTML = `
            <div class="pairs-loading">
                <div class="pairs-loading__spinner"></div>
                <p>Загрузка предложенных пар...</p>
            </div>
        `;
    }

    private showEmptyState(message: string) {
        this.pairsContainer.innerHTML = '';
        this.emptyState.style.display = 'block';

        const title = this.emptyState.querySelector('.empty-state__title');
        const text = this.emptyState.querySelector('.empty-state__text');

        if (title) title.textContent = 'Нет данных';
        if (text) text.textContent = message;
    }

    private showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.textContent = message;

        this.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    private escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new PairsApp();
});

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

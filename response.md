import { configureStore } from '@reduxjs/toolkit';
import { reviewApi } from '../reviewApi';
import { baseApi } from '../../api/baseApi';

/**
 * Type-safe mock for the base query arguments
 */
interface MockBaseQueryObject {
  url: string;
  method: string;
  data?: any;
  params?: any;
}

type MockBaseQueryArgs = MockBaseQueryObject | string;

// Mock the base query
const mockBaseQuery = jest.fn((_args: MockBaseQueryArgs): any => ({ data: [] }));

jest.mock('@/app/axios/axiosBaseQuery', () => ({
  axiosBaseQuery: () => (args: MockBaseQueryArgs) => mockBaseQuery(args),
}));

describe('reviewApi', () => {
  const createTestStore = () =>
    configureStore({
      reducer: {
        [baseApi.reducerPath]: baseApi.reducer,
      },
      middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
          serializableCheck: false,
        }).concat(baseApi.middleware),
    });

  type TestStore = ReturnType<typeof createTestStore>;
  let store: TestStore;

  beforeEach(() => {
    jest.useFakeTimers();
    mockBaseQuery.mockClear();
    store = createTestStore();
  });

  afterEach(() => {
    store.dispatch(baseApi.util.resetApiState());
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('should have all expected endpoints injected', () => {
    expect(reviewApi.endpoints.createReview).toBeDefined();
    expect(reviewApi.endpoints.getAllReviews).toBeDefined();
    expect(reviewApi.endpoints.getMyReceivedReviews).toBeDefined();
    expect(reviewApi.endpoints.getMyGivenReviews).toBeDefined();
    expect(reviewApi.endpoints.getReviewsByUserId).toBeDefined();
    expect(reviewApi.endpoints.getReviewById).toBeDefined();
    expect(reviewApi.endpoints.deleteReview).toBeDefined();
  });

  describe('endpoint execution', () => {
    it('createReview should call baseQuery with POST configuration', async () => {
      const mockReview = { rating: 5, comment: 'Great service' };
      const promise = store.dispatch(reviewApi.endpoints.createReview.initiate(mockReview));
      await promise;

      const firstCallArgs = mockBaseQuery.mock.calls[0][0] as MockBaseQueryObject;
      expect(firstCallArgs.url).toBe('/reviews/');
      expect(firstCallArgs.method).toBe('POST');
      expect(firstCallArgs.data).toEqual(mockReview);
    });

    it('getAllReviews should call baseQuery with params', async () => {
      const params = { page: 1, limit: 10 };
      const promise = store.dispatch(reviewApi.endpoints.getAllReviews.initiate(params));
      await promise;

      const firstCallArgs = mockBaseQuery.mock.calls[0][0] as MockBaseQueryObject;
      expect(firstCallArgs.url).toBe('/reviews/');
      expect(firstCallArgs.method).toBe('GET');
      expect(firstCallArgs.params).toEqual(params);

      promise.unsubscribe();
    });

    it('getReviewsByUserId should call baseQuery with correct URL', async () => {
      const userId = 'user_123';
      const promise = store.dispatch(reviewApi.endpoints.getReviewsByUserId.initiate(userId));
      await promise;

      const firstCallArgs = mockBaseQuery.mock.calls[0][0] as MockBaseQueryObject;
      expect(firstCallArgs.url).toBe(`/reviews/byuserid/${userId}`);
      expect(firstCallArgs.method).toBe('GET');
    });

    it('getReviewById should call baseQuery with correct URL', async () => {
      const reviewId = 'rev_456';
      const promise = store.dispatch(reviewApi.endpoints.getReviewById.initiate(reviewId));
      await promise;

      const firstCallArgs = mockBaseQuery.mock.calls[0][0] as MockBaseQueryObject;
      expect(firstCallArgs.url).toBe(`/reviews/${reviewId}`);
      expect(firstCallArgs.method).toBe('GET');
    });

    it('deleteReview should call baseQuery with DELETE configuration', async () => {
      const reviewId = 'rev_789';
      const promise = store.dispatch(reviewApi.endpoints.deleteReview.initiate(reviewId));
      await promise;

      const firstCallArgs = mockBaseQuery.mock.calls[0][0] as MockBaseQueryObject;
      expect(firstCallArgs.url).toBe(`/reviews/${reviewId}`);
      expect(firstCallArgs.method).toBe('DELETE');
    });
  });
});

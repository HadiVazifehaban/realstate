import { mutationOptions } from '@tanstack/react-query';
import { getQueryClient } from '@/lib/query-client';
import { createUser, updateUser, deleteUser } from './service';
import { userKeys } from './queries';
import type { UserMutationPayload } from './types';

export const createUserMutation = mutationOptions({
  mutationFn: (data: UserMutationPayload) => createUser(data),
  onSuccess: (data, variables, onMutateResult, context) => {
    getQueryClient().invalidateQueries({ queryKey: userKeys.all });
    return context;
  }
});

export const updateUserMutation = mutationOptions({
  mutationFn: ({ id, values }: { id: string; values: UserMutationPayload }) =>
    updateUser(id, values),
  onSuccess: (data, variables, onMutateResult, context) => {
    getQueryClient().invalidateQueries({ queryKey: userKeys.all });
    return context;
  }
});

export const deleteUserMutation = mutationOptions({
  mutationFn: (id: string) => deleteUser(id),
  onSuccess: () => {
    getQueryClient().invalidateQueries({ queryKey: userKeys.all });
  }
});

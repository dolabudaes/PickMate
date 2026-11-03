import { AppScreen } from '../../components/AppScreen';
import { PickiWorkspace } from '../../components/PickiWorkspace';

export default function PickiHomeScreen() {
  return (
    <AppScreen padded={false}>
      <PickiWorkspace />
    </AppScreen>
  );
}

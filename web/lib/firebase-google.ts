'use client';

import {getApp,getApps,initializeApp} from 'firebase/app';
import {GoogleAuthProvider,getAuth,signInWithPopup,signOut} from 'firebase/auth';

export class FirebaseClientConfigurationError extends Error {}

const config={
  apiKey:process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain:process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId:process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId:process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

function configured(){return Object.values(config).every(Boolean)}

function auth(){
  if(!configured())throw new FirebaseClientConfigurationError('Google sign-in is not configured for this environment.');
  return getAuth(getApps().length?getApp():initializeApp(config));
}

export async function signInWithGoogleForFirebase(){
  const result=await signInWithPopup(auth(),new GoogleAuthProvider());
  return result.user.getIdToken();
}

export async function signOutOfFirebase(){
  if(configured())await signOut(auth());
}

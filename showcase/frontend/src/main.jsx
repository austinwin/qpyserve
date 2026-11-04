import React from 'react';
import {createRoot} from 'react-dom/client';
import {Provider} from 'react-redux';
import {applyMiddleware, combineReducers, createStore} from 'redux';
import keplerGlReducer, {enhanceReduxMiddleware} from '@kepler.gl/reducers';
import App from './App.jsx';
import './index.css';

const store=createStore(
  combineReducers({
    keplerGl:keplerGlReducer.initialState({
      uiState:{currentModal:null,readOnly:false},
      mapState:{latitude:29.76,longitude:-95.37,zoom:10},
      mapStyle:{styleType:'carto-light'},
    }),
  }),
  applyMiddleware(...enhanceReduxMiddleware([])),
);
createRoot(document.getElementById('root')).render(<Provider store={store}><App/></Provider>);

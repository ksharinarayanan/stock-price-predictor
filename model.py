import requests
import pandas as pd
import numpy as np


def split_sequence(sequence, n_steps):
    X, y = list(), list()
    for i in range(len(sequence)):

        end_ix = i + n_steps

        if end_ix > len(sequence)-1:
            break

        seq_x, seq_y = sequence[i:end_ix], sequence[end_ix]
        X.append(seq_x)
        y.append(seq_y)

    return np.array(X), np.array(y)


def our_model(ticker, DAYS_TO_PREDICT):
    # API_KEY = 'TNIFPEE0JONTQTWW'
    API_KEY = 'EGRDO6ZSOEQXESVD'
    r = requests.get(
        'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol='+ticker+'&apikey='+API_KEY)

    df = pd.DataFrame.from_dict(r.json(), orient="index")
    df2 = (df.T['Time Series (Daily)'])

    df2 = df2.dropna()
    df_convert = df2.to_frame()
    df_index = list(df_convert.index)
    df2 = pd.json_normalize(df2)
    df2['Index'] = df_index
    df2 = df2.set_index('Index')
    df2 = df2[::-1]
    df2.index = pd.to_datetime(df2.index)
    df2['1. open'] = pd.to_numeric(df2['1. open'])
    df2['2. high'] = pd.to_numeric(df2['2. high'])
    df2['3. low'] = pd.to_numeric(df2['3. low'])
    df2['4. close'] = pd.to_numeric(df2['4. close'])
    df2['5. volume'] = pd.to_numeric(df2['5. volume'])

    seq_length = 5

    data = np.array(df2['4. close'])

    X, y = split_sequence(data, seq_length)

    n_features = 1
    X = X.reshape((X.shape[0], X.shape[1], n_features))

    import tensorflow as tf

    from keras.models import Sequential
    from keras.layers import Flatten, Dense
    # the data is 1-dimensional so we will use a 1d convolution layer
    from keras.layers.convolutional import Conv1D, MaxPooling1D

    model = Sequential()

    model.add(Conv1D(filters=64, kernel_size=2, activation='relu',
                     input_shape=(seq_length, n_features)))

    model.add(MaxPooling1D(pool_size=2))

    model.add(Flatten())

    model.add(Dense(50, activation='relu'))

    model.add(Dense(1))

    model.compile(optimizer='adam', loss='mse')

    model.fit(X, y, epochs=100)

    test_seq = X[-1:]
    preds = []

    for _ in range(DAYS_TO_PREDICT):
        y_test_pred = model.predict(test_seq)
        pred = y_test_pred
        preds.append(y_test_pred)
        new_seq = test_seq.flatten()
        new_seq = np.append(new_seq, [pred])
        new_seq = new_seq[1:]
        test_seq = new_seq.reshape(1, seq_length, 1)
    preds = np.array(preds).reshape(DAYS_TO_PREDICT,)

    predicted_index = pd.date_range(
        start=df2.index[-2],
        periods=DAYS_TO_PREDICT+1,
        closed='right')

    predicted_price = pd.Series(
        data=preds,
        index=predicted_index)

    return predicted_price
